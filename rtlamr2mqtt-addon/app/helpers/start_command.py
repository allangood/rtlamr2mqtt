import subprocess
import threading
import time
import sys

def read_output(pipe):
    """Reads lines from a pipe and prints them."""
    for line in iter(pipe.readline, b''):
        print(f"Child output: {line.decode().strip()}")

def run_background_process(command):
    """Starts a process in the background and reads its output in a separate thread."""
    try:
        # bufsize=1 for line-buffering
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=False # Read as bytes, then decode
        )

        # Start a thread to read stdout
        stdout_thread = threading.Thread(target=read_output, args=(process.stdout,))
        stdout_thread.daemon = True # Allows the main program to exit even if the thread is still running
        stdout_thread.start()

        # You can optionally read stderr in another thread if needed
        stderr_thread = threading.Thread(target=read_output, args=(process.stderr,))
        stderr_thread.daemon = True
        stderr_thread.start()

        print(f"Process {process.pid} started in background.")

        # Do other work in the main thread
        for i in range(5):
            print(f"Main thread doing work: {i}")
            time.sleep(1)

        # Wait for the process to finish (optional, depending on your needs)
        # If you don't call .wait(), the main thread might exit before the child process is done
        process.wait()
        stdout_thread.join() # Wait for the stdout reading thread to finish
        stderr_thread.join() # Wait for the stdout reading thread to finish
        print(f"Process {process.pid} finished with exit code {process.returncode}.")

    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Example: Run a simple shell command that prints lines with delays
    # For a Python script, you might use: ['python', '-u', 'your_script.py']
    # The '-u' flag makes Python streams unbuffered.
    command_to_run = ['bash', '-c', 'for i in $(seq 1 5); do echo "Line $i from child"; sleep 0.5; echo "Err" >&2; sleep 0.5; done']
    run_background_process(command_to_run)
