#!/bin/bash

# Function to handle cleanup on exit
cleanup() {
    echo "Shutting down services..."
    # Kill background processes
    jobs -p | xargs -r kill
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

echo "Starting combined task-runner and file-tracker services..."

# Start file-tracker in the background
echo "Starting file-tracker..."
cd /file-tracker
python ./file_tracker/main.py &
FILE_TRACKER_PID=$!

# Start task-runner in the background
echo "Starting task-runner..."
cd /task-runner
python ./task_runner/main.py &
TASK_RUNNER_PID=$!

echo "Both services started:"
echo "  - File-tracker PID: $FILE_TRACKER_PID"
echo "  - Task-runner PID: $TASK_RUNNER_PID"

# Wait for either process to exit
wait $FILE_TRACKER_PID $TASK_RUNNER_PID

# If we get here, one of the services exited
echo "One of the services exited. Cleaning up..."
cleanup
