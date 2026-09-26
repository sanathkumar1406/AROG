filepath = r'c:\sanath\projects\Arog\frontend\arog_sign_in_clinical_portal\code.html'

with open(filepath, 'rb') as f:
    content = f.read()

# The corrupted sequence in bytes
old = b'</\x3cscript src="/frontend/api.js"\x3e\x3c/script\x3e'
new = b'</div>\r\n</div>\r\n</div>\r\n</div>\r\n</div>\r\n<script src="/frontend/api.js"></script>'

content = content.replace(old, new)

with open(filepath, 'wb') as f:
    f.write(content)

print("Fixed!")
