import sys

from .celery_app import celery_app


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = ["worker", "--loglevel=info"]
    elif args[0] != "worker":
        args = ["worker", *args]
    return celery_app.worker_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
