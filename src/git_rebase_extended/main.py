import sys


def main():
    if "--help" in sys.argv:
        print(
            "A CLI for performing interactive rebases with extra features.\n"
            "\n"
            "Arguments will be passed to `git rebase`.\n"
        )


if __name__ == "__main__":
    main()
