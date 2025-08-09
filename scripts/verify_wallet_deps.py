import sys

def main():
    ok = True
    try:
        import pyotp  # noqa: F401
        print("OK import pyotp")
    except Exception as e:
        ok = False
        print(f"FAIL import pyotp: {e}", file=sys.stderr)

    try:
        import qrcode  # noqa: F401
        print("OK import qrcode")
    except Exception as e:
        ok = False
        print(f"FAIL import qrcode: {e}", file=sys.stderr)

    try:
        from PIL import Image  # noqa: F401
        print("OK import Pillow (PIL)")
    except Exception as e:
        ok = False
        print(f"FAIL import Pillow: {e}", file=sys.stderr)

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
