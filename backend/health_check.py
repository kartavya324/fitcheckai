"""
Run this before starting the server to verify 
everything is correctly installed and configured.
Usage: python health_check.py
"""
import sys
from pathlib import Path

def check(name, fn):
    try:
        result = fn()
        try:
            print(f"  ✅ {name}: {result}")
        except UnicodeEncodeError:
            print(f"  [OK] {name}: {result}")
        return True
    except Exception as e:
        try:
            print(f"  ❌ {name}: {e}")
        except UnicodeEncodeError:
            print(f"  [FAIL] {name}: {e}")
        return False

print("\n" + "="*50)
print("FitCheck AI — System Health Check")
print("="*50 + "\n")

all_ok = True

print("Python packages:")
all_ok &= check("torch", lambda: __import__("torch").__version__)
all_ok &= check("CUDA", lambda: (
    "available" if __import__("torch").cuda.is_available() 
    else (_ for _ in ()).throw(Exception("CUDA not available"))
))
all_ok &= check("GPU name", lambda: 
    __import__("torch").cuda.get_device_name(0)
)
all_ok &= check("trimesh", lambda: __import__("trimesh").__version__)
all_ok &= check("PIL", lambda: __import__("PIL").__version__)
all_ok &= check("flask", lambda: __import__("flask").__version__)
all_ok &= check("rembg", lambda: "OK")
all_ok &= check("scipy", lambda: __import__("scipy").__version__)
all_ok &= check("numpy", lambda: __import__("numpy").__version__)

print("\nFiles:")
base = Path(__file__).parent
all_ok &= check("pifuhd_server.py", 
    lambda: "exists" if (base/"pifuhd_server.py").exists() 
    else (_ for _ in ()).throw(Exception("missing")))
all_ok &= check("texture_projection.py",
    lambda: "exists" if (base/"texture_projection.py").exists()
    else (_ for _ in ()).throw(Exception("missing")))
all_ok &= check("PIFuHD repo",
    lambda: "exists" if (base/"pifuhd").exists()
    else (_ for _ in ()).throw(Exception("missing - run run_windows.bat")))
all_ok &= check("PIFuHD weights",
    lambda: "exists" if (base/"pifuhd/checkpoints/pifuhd.pt").exists()
    else (_ for _ in ()).throw(Exception("missing - run run_windows.bat")))

print("\nImport test:")
all_ok &= check("pifuhd_server imports",
    lambda: __import__("pifuhd_server") and "OK")
all_ok &= check("texture_projection imports", 
    lambda: __import__("texture_projection") and "OK")

print("\n" + "="*50)
if all_ok:
    try:
        print("✅ ALL CHECKS PASSED — Ready to start server!")
    except UnicodeEncodeError:
        print("ALL CHECKS PASSED — Ready to start server!")
    print("Run: start_pifuhd_server.bat")
else:
    try:
        print("❌ SOME CHECKS FAILED — Fix errors above first")
    except UnicodeEncodeError:
        print("SOME CHECKS FAILED — Fix errors above first")
    print("Then run: python health_check.py again")
print("="*50 + "\n")
