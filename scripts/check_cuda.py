import sys

import psutil
import torch


def check_cuda():
    print("--- SYSTEM CHECK ---")
    print(f"Python Version: {sys.version}")
    print(f"PyTorch Version: {torch.__version__}")
    if hasattr(torch, "version") and hasattr(torch.version, "cuda"):
        print(f"PyTorch CUDA Version: {torch.version.cuda}")

    cuda_available = torch.cuda.is_available()
    print(f"CUDA Available: {cuda_available}")

    if cuda_available:
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        total_vram = props.total_memory / (1024**3)
        print(f"Total VRAM: {total_vram:.2f} GB")

        # Check current allocation
        reserved = torch.cuda.memory_reserved(0) / (1024**3)
        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        reserved - allocated

        print(f"VRAM Reserved by PyTorch: {reserved:.2f} GB")
        print(f"VRAM Allocated: {allocated:.2f} GB")

        # Test allocation
        try:
            print("Attempting to allocate 100MB on CUDA...")
            x = torch.zeros((1024, 1024, 25), device="cuda")
            print("✅ CUDA Allocation Successful.")
            del x
            torch.cuda.empty_cache()
        except Exception as e:
            print(f"❌ CUDA Allocation Failed: {e}")
    else:
        print("❌ CUDA is NOT detected by PyTorch. Check drivers and 'nvidia-smi'.")

    print("\n--- RAM CHECK ---")
    mem = psutil.virtual_memory()
    print(f"Total RAM: {mem.total / (1024**3):.2f} GB")
    print(f"Available RAM: {mem.available / (1024**3):.2f} GB")
    print(f"Percent Used: {mem.percent}%")


if __name__ == "__main__":
    check_cuda()
