from solution.common.paths import KEY_FILE, WORK_DIR, ensure_base_dirs
from solution.decrypt.guess_key import guess_key


def main() -> None:
    ensure_base_dirs()
    print(guess_key(WORK_DIR / "ysbin", KEY_FILE))


if __name__ == "__main__":
    main()
