import subprocess
import os
import argparse
import time
import logging
import sys

def is_unix_like() -> bool:
    return os.name != 'nt'

def check_if_process_running(process_name: str) -> bool:
    if is_unix_like():
        logger.debug("Checking if process '%s' is running on Unix-like system", process_name)
        return subprocess.run(['pgrep', '-x', 'ping'], capture_output=True, text=True).returncode == 0
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
    return parser.parse_args()

def loop(target: str, interval_s: int = 10) -> None:
    if check_if_process_running(target):
        logger.info("Process '%s' is running.", target)
    else:
        logger.info("Process '%s' is not running.", target)

    logger.debug("Sleeping for %d seconds before next check", interval_s)
    time.sleep(interval_s)

global logger
if __name__ == "__main__":
    args: argparse.Namespace = parse_args()
    logger: logging.Logger = init_logger(args.log_level)

    logger.debug('Parsed arguments: %s', args)
    logger.info('Starting process monitoring for: %s', args.target)
    try:
        while True:
            loop(args.target, interval_s=args.interval)
    except KeyboardInterrupt:
        logger.info('Stopping process monitoring for: %s', args.target)
        sys.exit(0)