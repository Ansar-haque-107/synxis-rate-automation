import sys
from synxis import export, push


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if not mode:
        mode = input("e = export, p = push. Type e/p: ").strip().lower()

    if mode in ("export", "e"):
        export.run()
    elif mode in ("push", "p"):
        push.run()
    else:
        print("Unknown choice. Run again and type e or p.")


if __name__ == "__main__":
    main()
