from __future__ import absolute_import, unicode_literals

import sys


__all__ = ['simple_main', 'django_main']


if sys.path[0] and not sys.path[0].endswith('/bin'):
    # When Python is invoked using `python -m some_module`, the first item in the path is always empty
    # When Python is invoked using an entry-point binary, the first item in the path is a /bin folder somewhere
    # When Python is invoked using `python /path/to/file.py`, the first item in the path is `/path/to`, which is bad
    print(
        'ERROR: You have triggered a double-import trap (see '
        'http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html#the-double-import-trap '
        'for more information on what this is). In short, you cannot start this service with '
        '`python /path/to/standalone.py`, because that puts all the modules in this service on the path as top-level '
        'modules, potentially masking builtins and breaking all sorts of things with hard-to-diagnose errors. Instead, '
        'you must start this service with `python -m module.to.standalone` or by simply calling the `service_name` '
        'entry point executable.'
    )
    exit(99)


def _get_arg_parser():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--fork-processes', '--fork',
        help='The number of processes to fork (if 0, 1, or none, no process is forked; the server is run directly)',
        required=False,
        type=int,
        default=0,
    )
    return parser


def _get_args(parser):
    return parser.parse_known_args()[0]


def _run_server(args, server_class):
    if args.fork_processes > 1:
        import multiprocessing
        import signal
        import time

        processes = []
        cmd = {'keep_starting': True}

        def _stop(*_):
            cmd['keep_starting'] = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        for i in range(0, args.fork_processes):
            process = multiprocessing.Process(target=server_class.main, name='pysoa-worker-{}'.format(i))

            if not cmd['keep_starting']:
                # Got shutdown signal while starting up, so don't keep starting up
                break

            processes.append(process)
            process.start()
            time.sleep(0.3)

        for process in processes:
            process.join()
    else:
        server_class.main()


def simple_main(server_getter):
    """
    Call this within __main__ to start the service as a standalone server without Django support. Your server should
    not have `use_django=True`. If it does, see `django_main`, instead.

    :param server_getter: A callable that returns the service's Server class (not an instance of it)
    """
    _run_server(_get_args(_get_arg_parser()), server_getter())


def django_main(server_getter):
    """
    Call this within __main__ to start the service as a standalone server with Django support. Your server should have
    `use_django=True`. If it does not, see `simple_main`, instead.

    :param server_getter: A callable that returns the service's Server class (not an instance of it). Your service code
                          should not be imported until the `server_getter` callable is called, otherwise Django errors
                          will occur.
    """
    import os
    import django

    parser = _get_arg_parser()
    parser.add_argument(
        '-s', '--settings',
        help='The settings module to use (must be importable)',
        required='DJANGO_SETTINGS_MODULE' not in os.environ,  # if env var does not exist, this argument is required
    )
    args = _get_args(parser)
    if args.settings:
        os.environ['DJANGO_SETTINGS_MODULE'] = args.settings

    if django.VERSION >= (1, 7):
        django.setup()

    _run_server(args, server_getter())
