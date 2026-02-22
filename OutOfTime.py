import argparse
import logging
import os
from plyer import notification
import subprocess
import sys
import time
import threading


def is_unix_like() -> bool:
    return os.name != 'nt'


def check_if_process_running(process_name: str) -> bool:
    if is_unix_like():
        logger.debug("Checking if process '%s' is running on Unix-like system", process_name)
        return subprocess.run(['pgrep', '-x', process_name], capture_output=True, text=True).returncode == 0
    else:
        ###TODO, check this works, it should check if a process is running with the given name
        logger.debug("Checking if process '%s' is running on Windows system", process_name)
        return process_name in subprocess.run(['tasklist'], capture_output=True, text=True).stdout


def close_process(process_name: str) -> bool:
    if is_unix_like():
        logger.debug("Attempting to kill process '%s' on Unix-like system", process_name)
        return subprocess.run(['killall', process_name], capture_output=True, text=True).returncode == 0
    else:
        ###TODO, check this works, it should kill all processes with the given name
        logger.debug("Attempting to kill process '%s' on Windows system", process_name)
        return subprocess.run(['taskkill', '/IM', process_name], capture_output=True, text=True).returncode == 0


def init_logger(level_string: str) -> logging.Logger:
    level: int = logging.getLevelNamesMapping().get(level_string.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],

    )
    new_logger: logging.Logger = logging.getLogger('OutOfTime')
    new_logger.debug('Initialized logger with level: %s', level_string)
    return new_logger


def parse_args() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Check and close a process by name.")
    parser.add_argument('target',
                        help="Name of the process to check/close",
                        default=None)
    parser.add_argument('--log_level', '-l',
                        help="Level of detail in which to log the output",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO')
    parser.add_argument('--interval', '-i',
                        help="Interval in which to poll the process status, in seconds",
                        type=int,
                        default=10)
    parser.add_argument('--timeout', '-t',
                        help="Length of time in which the program is allowed to run, in seconds",
                        type=int,
                        default=3600)
    parser.add_argument('--remind', '-r',
                        help="The amount of time left until timeout in which a notification should be displayed, in seconds",
                        type=int,
                        default=300)
    return parser.parse_args()


def notify(title:str, message:str, timeout_s: int = 10) -> None:
    logger.debug("Sending notification: %s", message)
    notification.notify(
        app_name='OutOfTime',
        title=title,
        message=message,
        timeout=timeout_s
    )


def handle_timeout(target: str, run_limit_s: int) -> None:
    logger.info("Runtime limit of %d seconds reached. Attempting to close process '%s'.", run_limit_s, target)
    notify("Process Timeout", f"Process '{target}' has reached the runtime limit of {run_limit_s} seconds and will be closed.")
    if close_process(target):
        logger.info("Process '%s' closed successfully.", target)
    else:
        logger.warning("Failed to close process '%s'. It may not be running or there may be insufficient permissions.", target)


def handle_reminder(target: str, run_limit_s: int) -> None:
    global warning_sent
    time_left_s: int = run_limit_s - runtime_s
    logger.info("Process '%s' is running and approaching runtime limit. Time left: %d seconds.", target, time_left_s)
    if not warning_sent:
        notify('Process Runtime Warning', f"Process '{target}' has been running for {runtime_s} seconds. Time left until timeout: {time_left_s} seconds.")
        warning_sent = True


def loop(target: str, run_limit_s: int, remind_time_s: int, interval_s: int = 10) -> None:
    global runtime_s
    global warning_sent

    is_running: bool = check_if_process_running(target)

    if runtime_s >= run_limit_s and is_running:
        handle_timeout(target, run_limit_s)
        return
    elif is_running and runtime_s >= (run_limit_s - remind_time_s):
        handle_reminder(target, run_limit_s)

    if is_running:
        logger.info("Process '%s' is running.", target)
        runtime_s = runtime_s + interval_s
    else:
        logger.info("Process '%s' is not running.", target)

    logger.debug("Sleeping for %d seconds before next check", interval_s)
    time.sleep(interval_s)

    logger.info("Total runtime: %d seconds", runtime_s)


global logger
runtime_s = 0
warning_sent = False

# Threading / programmatic monitor state
_monitor_thread = None
_stop_event: threading.Event | None = None
_monitor_lock = threading.Lock()


def run_monitor(stop_event: threading.Event, target: str, run_limit_s: int, remind_time_s: int, interval_s: float = 10.0, log_level: str = 'INFO') -> None:
    """
    Blocking monitor loop suitable to run in a background thread. Exits when stop_event is set.
    """
    global logger, runtime_s, warning_sent
    logger = init_logger(log_level)
    runtime_s = 0
    warning_sent = False

    logger.info('Starting threaded monitor for: %s', target)
    notify("Process Monitor Started", f"Monitoring process '{target}' with a timeout of {run_limit_s} seconds.")

    try:
        while not stop_event.is_set():
            # perform one monitoring step (mirrors loop behaviour)
            is_running: bool = check_if_process_running(target)

            if runtime_s >= run_limit_s and is_running:
                handle_timeout(target, run_limit_s)
                return
            elif is_running and runtime_s >= (run_limit_s - remind_time_s):
                handle_reminder(target, run_limit_s)

            if is_running:
                logger.info("Process '%s' is running.", target)
                runtime_s = runtime_s + interval_s
            else:
                logger.info("Process '%s' is not running.", target)

            logger.debug("Waiting for %s seconds or until stop event", interval_s)
            # wait returns True if event set during wait
            stop_event.wait(interval_s)

            logger.info("Total runtime: %d seconds", runtime_s)

    except Exception as e:
        logger.exception('Unhandled exception in monitor thread: %s', e)
        notify('Monitor Error', f'An error occurred in the monitor: {e}')

    logger.info('Monitor stopped for: %s', target)


def start_monitor(target: str, timeout: int = 3600, interval: float = 10.0, remind: int = 300, log_level: str = 'INFO') -> threading.Thread | None:
    """
    Start the monitor in a background thread. Returns the Thread object or None if already running or invalid input.
    """
    global _monitor_thread, _stop_event, logger

    if not target or not target.strip():
        raise ValueError('target must be a non-empty process name')

    with _monitor_lock:
        if _monitor_thread is not None and _monitor_thread.is_alive():
            logger = init_logger(log_level)
            logger.warning('Monitor already running')
            return _monitor_thread

        _stop_event = threading.Event()
        _monitor_thread = threading.Thread(target=run_monitor, args=(_stop_event, target, timeout, remind, interval, log_level), daemon=False)
        _monitor_thread.start()
        return _monitor_thread


def stop_monitor(timeout: float = 2.0) -> bool:
    """
    Signal the monitor thread to stop and join it. Returns True if stopped cleanly.
    """
    global _monitor_thread, _stop_event

    with _monitor_lock:
        if _monitor_thread is None:
            return True
        if _stop_event is None:
            return True

        _stop_event.set()
        _monitor_thread.join(timeout=timeout)
        still_alive = _monitor_thread.is_alive()
        if still_alive:
            logger.warning('Monitor thread did not stop within timeout')
            return False

        _monitor_thread = None
        _stop_event = None
        return True



if __name__ == "__main__":
    args: argparse.Namespace = parse_args()
    logger: logging.Logger = init_logger(args.log_level)

    logger.debug('Parsed arguments: %s', args)
    logger.info('Starting process monitoring for: %s', args.target)
    notify("Process Monitor Started", f"Monitoring process '{args.target}' with a timeout of {args.timeout} seconds.")
    try:
        while True:
            loop(args.target, args.timeout, args.remind, interval_s=args.interval)
    except KeyboardInterrupt:
        logger.info('Received Manual Interrupt - Stopping process monitoring for: %s', args.target)
        sys.exit(0)