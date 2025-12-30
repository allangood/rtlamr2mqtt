import subprocess
import threading
import time
import sys


class backgroundProcess:
    def __init__(self):
        self.buffer = 500
        self.output = []
        self.process = None

    def read_output(self, pipe):
        """Reads lines from a pipe and prints them."""
        for line in iter(pipe.readline, b''):
            """ If content >= buffer, cleans the buffer """
            if len(self.output) >= self.buffer:
                self.output.clear()
            self.output.apped(line.decode().strip())

    def get_output(self):
        return self.output
    
    def clear_buffer(self):
        self.output.clear()

    def run(self, command):
        """Starts a process in the background and reads its output in a separate thread."""
        try:
            # bufsize=1 for line-buffering
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=False # Read as bytes, then decode
            )

            # Start a thread to read stdout
            stdout_thread = threading.Thread(target=self.read_output, args=(self.process.stdout,))
            stdout_thread.daemon = True # Allows the main program to exit even if the thread is still running
            stdout_thread.start()

            # You can optionally read stderr in another thread if needed
            stderr_thread = threading.Thread(target=self.read_output, args=(self.process.stderr,))
            stderr_thread.daemon = True
            stderr_thread.start()

            stdout_thread.join()
            stderr_thread.join()

        except FileNotFoundError:
            print(f"Error: Command '{command[0]}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

'''
How to use it
command_to_run = ['bash', '-c', 'for i in $(seq 1 5); do echo "Line $i from child"; sleep 0.5; echo "Err" >&2; sleep 0.5; done']
run_background_process(command_to_run)
'''