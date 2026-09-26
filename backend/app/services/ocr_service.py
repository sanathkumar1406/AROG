"""
AROG OCR Service - Uses existing TrOCR ONNX model for text extraction.

Model: trocr-onnx-float (encoder.onnx + decoder.onnx)
- Encoder: Takes pixel_values [1, 3, 384, 384] float32 (range 0-1)
           Outputs: 6 cross-attention KV caches [1, 8, 578, 32]
- Decoder: Autoregressive, takes input_ids + index + KV caches
           Outputs: next_token + updated KV caches
"""
import os
import json
import numpy as np
from PIL import Image

# Lazy-loaded ONNX sessions
_encoder_session = None
_decoder_session = None
_metadata = None

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "trocr-onnx-float"
)

# TrOCR uses GPT-2 style BPE tokenizer. For the ONNX export, tokens are integer IDs.
# Standard TrOCR special tokens:
BOS_TOKEN_ID = 2   # <s> / beginning of sequence
EOS_TOKEN_ID = 2   # </s> / end of sequence (same as BOS for many TrOCR models)
PAD_TOKEN_ID = 1
MAX_LENGTH = 20     # Max tokens to generate (matches KV cache dim: 19 initial + grows)


def _load_metadata():
    """Load model metadata."""
    global _metadata
    if _metadata is None:
        meta_path = os.path.join(MODEL_DIR, "metadata.json")
        with open(meta_path, "r") as f:
            _metadata = json.load(f)
    return _metadata


def _get_encoder():
    """Lazy-load ONNX encoder session."""
    global _encoder_session
    if _encoder_session is None:
        import onnxruntime as ort
        encoder_path = os.path.join(MODEL_DIR, "encoder.onnx")
        if not os.path.exists(encoder_path):
            raise FileNotFoundError(f"Encoder model not found at {encoder_path}")
        _encoder_session = ort.InferenceSession(
            encoder_path,
            providers=["CPUExecutionProvider"]
        )
    return _encoder_session


def _get_decoder():
    """Lazy-load ONNX decoder session."""
    global _decoder_session
    if _decoder_session is None:
        import onnxruntime as ort
        decoder_path = os.path.join(MODEL_DIR, "decoder.onnx")
        if not os.path.exists(decoder_path):
            raise FileNotFoundError(f"Decoder model not found at {decoder_path}")
        _decoder_session = ort.InferenceSession(
            decoder_path,
            providers=["CPUExecutionProvider"]
        )
    return _decoder_session


def preprocess_image(image: Image.Image) -> np.ndarray:
    """
    Preprocess image for TrOCR encoder.
    Resize to 384x384, normalize to [0, 1], convert to CHW format.
    """
    # Convert to RGB if needed
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Resize to 384x384 (model input size from metadata)
    image = image.resize((384, 384), Image.BILINEAR)

    # Convert to numpy, normalize to [0, 1]
    img_array = np.array(image, dtype=np.float32) / 255.0

    # HWC -> CHW
    img_array = np.transpose(img_array, (2, 0, 1))

    # Add batch dimension: [1, 3, 384, 384]
    img_array = np.expand_dims(img_array, axis=0)

    return img_array


def run_ocr(image: Image.Image) -> dict:
    """
    Run TrOCR inference on an image.

    Returns dict with:
        - extracted_text: The recognized text
        - confidence: Approximate confidence (None if not available)
    """
    try:
        encoder = _get_encoder()
        decoder = _get_decoder()
    except Exception as e:
        return {
            "extracted_text": "",
            "confidence": None,
            "error": f"Failed to load OCR model: {str(e)}"
        }

    # Preprocess image
    pixel_values = preprocess_image(image)

    # Run encoder
    encoder_inputs = {"pixel_values": pixel_values}
    encoder_outputs = encoder.run(None, encoder_inputs)

    # Map encoder outputs to cross-attention KV caches
    encoder_output_names = [o.name for o in encoder.get_outputs()]
    cross_kv = {}
    for name, value in zip(encoder_output_names, encoder_outputs):
        cross_kv[name] = value

    # Autoregressive decoding
    # Initialize decoder inputs
    input_ids = np.array([[BOS_TOKEN_ID]], dtype=np.int32)  # [1, 1]
    index = np.array([0], dtype=np.int32)  # [1]

    # Initialize self-attention KV caches with zeros (first step has no history)
    # From metadata: kv_N_attn_key/val shape [1, 8, 19, 32]
    # But on first step we need empty caches, so use shape [1, 8, 0, 32]
    # Actually, looking at the metadata the decoder expects [1, 8, 19, 32] fixed shape
    # We need to pad with zeros for the initial state
    num_layers = 6
    num_heads = 8
    head_dim = 32
    max_seq_len = 19  # from metadata

    generated_tokens = []
    all_log_probs = []

    for step in range(MAX_LENGTH):
        decoder_inputs = {
            "input_ids": input_ids,
            "index": index,
        }

        # Add self-attention KV caches
        for layer_idx in range(num_layers):
            if step == 0:
                # Initialize with zeros
                decoder_inputs[f"kv_{layer_idx}_attn_key"] = np.zeros(
                    (1, num_heads, max_seq_len, head_dim), dtype=np.float32
                )
                decoder_inputs[f"kv_{layer_idx}_attn_val"] = np.zeros(
                    (1, num_heads, max_seq_len, head_dim), dtype=np.float32
                )
            else:
                decoder_inputs[f"kv_{layer_idx}_attn_key"] = attn_kv_caches[f"kv_cache_key_{layer_idx}"][:, :, :max_seq_len, :]
                decoder_inputs[f"kv_{layer_idx}_attn_val"] = attn_kv_caches[f"kv_cache_val_{layer_idx}"][:, :, :max_seq_len, :]

            # Cross-attention KV caches from encoder (constant)
            decoder_inputs[f"kv_{layer_idx}_cross_attn_key"] = cross_kv.get(
                f"kv_cache_key_{layer_idx}",
                np.zeros((1, num_heads, 578, head_dim), dtype=np.float32)
            )
            decoder_inputs[f"kv_{layer_idx}_cross_attn_val"] = cross_kv.get(
                f"kv_cache_val_{layer_idx}",
                np.zeros((1, num_heads, 578, head_dim), dtype=np.float32)
            )

        # Run decoder
        decoder_outputs = decoder.run(None, decoder_inputs)
        decoder_output_names = [o.name for o in decoder.get_outputs()]

        # Parse outputs
        attn_kv_caches = {}
        next_token = None
        for name, value in zip(decoder_output_names, decoder_outputs):
            if name == "next_token":
                next_token = int(value[0])
            else:
                attn_kv_caches[name] = value

        if next_token is None:
            break

        # Check for EOS
        if next_token == EOS_TOKEN_ID and step > 0:
            break

        generated_tokens.append(next_token)

        # Update for next step
        input_ids = np.array([[next_token]], dtype=np.int32)
        index = np.array([step + 1], dtype=np.int32)

    # Decode tokens to text
    extracted_text = _decode_tokens(generated_tokens)
    extracted_clean = extracted_text.strip()
    structured = parse_structured_fields(extracted_clean)

    return {
        "extracted_text": extracted_clean,
        "structured_data": structured,
        "confidence": None,  # ONNX model doesn't expose logits directly
    }


def parse_structured_fields(text: str) -> dict:
    """
    Parse OCR extracted text into structured clinical fields (Requirement 17).
    Extracts: patient_name, date, medicine, dosage, notes, follow_up.
    """
    import re
    if not text:
        return {}

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    structured = {
        "patient_name": None,
        "date": None,
        "medicine": None,
        "dosage": None,
        "notes": None,
        "follow_up": None,
    }

    # 1. Patient Name
    pt_match = re.search(r'(?:patient|pt|name|mr\.|mrs\.|ms\.)\s*[:\-]?\s*([A-Za-z\s\.\']{3,35})', text, re.IGNORECASE)
    if pt_match:
        structured["patient_name"] = pt_match.group(1).strip()

    # 2. Date
    date_match = re.search(
        r'(?:date|dt)\s*[:\-]?\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{2,4})',
        text,
        re.IGNORECASE,
    )
    if not date_match:
        date_match = re.search(r'\b([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{2,4})\b', text, re.IGNORECASE)
    if date_match:
        structured["date"] = date_match.group(1).strip()

    # 3. Dosage
    dosage_match = re.search(r'\b([0-9]+(?:\.[0-9]+)?\s*(?:mg|mcg|g|ml|tablets?|capsules?)(?:\s+(?:OD|BD|TDS|QDS|once\s+daily|twice\s+daily))?)\b', text, re.IGNORECASE)
    if dosage_match:
        structured["dosage"] = dosage_match.group(1).strip()

    # 4. Medicine
    med_match = re.search(r'(?:medicine|medication|rx|drug|prescribed|tab|cap|syrup)\s*[:\-]?\s*([A-Za-z0-9\s\-]+?)(?=\s+(?:dosage|dose|notes|date|follow|review)|$|\n)', text, re.IGNORECASE)
    if med_match:
        structured["medicine"] = med_match.group(1).strip()
    else:
        # Check against common clinical medications
        common_meds = [
            "Amlodipine", "Ramipril", "Metformin", "Paracetamol", "Atorvastatin",
            "Hydrochlorothiazide", "Losartan", "Omeprazole", "Amoxicillin",
            "Ciprofloxacin", "Aspirin", "Cetirizine", "Azithromycin", "Ibuprofen"
        ]
        for m in common_meds:
            if re.search(rf'\b{m}\b', text, re.IGNORECASE):
                structured["medicine"] = m
                break

    # 5. Follow-up
    fu_match = re.search(r'(?:follow[\s\-]*up|review|next\s+visit)\s*[:\-]?\s*([^\n\r;\.]+)', text, re.IGNORECASE)
    if fu_match:
        structured["follow_up"] = fu_match.group(1).strip()

    # 6. Notes
    notes_match = re.search(r'(?:notes|complaint|diagnosis|instructions|plan)\s*[:\-]?\s*([^\n\r]+)', text, re.IGNORECASE)
    if notes_match:
        structured["notes"] = notes_match.group(1).strip()
    elif not structured["medicine"] and not structured["patient_name"]:
        # Fallback if no keys found: the text itself can serve as notes
        structured["notes"] = text

    return structured


_tokenizer = None


def _get_tokenizer():
    """Lazy-load and cache the tokenizer."""
    global _tokenizer
    if _tokenizer is None:
        try:
            from transformers import AutoTokenizer
            # Try loading from local cache first
            try:
                _tokenizer = AutoTokenizer.from_pretrained("microsoft/trocr-base-handwritten", local_files_only=True)
            except Exception:
                _tokenizer = AutoTokenizer.from_pretrained("microsoft/trocr-base-handwritten")
        except Exception:
            _tokenizer = None
    return _tokenizer


def _decode_tokens(token_ids: list) -> str:
    """
    Decode token IDs to text using the cached TrOCR tokenizer.
    """
    tok = _get_tokenizer()
    if tok is not None:
        try:
            return tok.decode(token_ids, skip_special_tokens=True)
        except Exception:
            pass

    # Fallback: basic ASCII mapping for common character tokens
    text_chars = []
    for tid in token_ids:
        if 0 <= tid < 256:
            text_chars.append(chr(tid))
        elif tid >= 256:
            text_chars.append("?")
    return "".join(text_chars)

