try:
    import flask
    print("flask OK:", flask.__version__)
except ImportError as e:
    print("flask MISSING:", e)

try:
    import flask_cors
    print("flask_cors OK")
except ImportError as e:
    print("flask_cors MISSING:", e)

try:
    import trimesh
    print("trimesh OK:", trimesh.__version__)
except ImportError as e:
    print("trimesh MISSING:", e)

try:
    import numpy
    print("numpy OK:", numpy.__version__)
except ImportError as e:
    print("numpy MISSING:", e)

try:
    import torch
    print("torch OK:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
except ImportError as e:
    print("torch MISSING:", e)
