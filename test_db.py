import sys
import os
from cryptography.fernet import Fernet

key = "mwqVH_ai0ZtuiKFJhWr0uZnUxtmfHBJ0CJqMY3RcmMY="
fernet = Fernet(key.encode())

encrypted_pat = "gAAAAABqlr8aUD73-upa4ZymZ3DyblwejY9zO4ooMRj73PC8w-vqNtBM7MwLnv5B2Ukknpyjs0s9mLfofcvu_iECCLIvSPbqtO_QHTE_t7bPHhmJsK5Ix8Gc2A6oOqfC9ikQt3hMG46g"

try:
    pat = fernet.decrypt(encrypted_pat.encode()).decode()
    print(f"Decrypted PAT: {pat}")
except Exception as e:
    print(f"Decrypt failed: {e}")
