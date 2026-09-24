# CPU Scheduling Simulator

This is a CPU Scheduling Simulator developed for an Operating Systems lab.

The program allows the user to upload an Excel file containing 1,500 processes with:

* Process ID
* Arrival Time
* Burst Time
* Priority

## Scheduling Algorithms

The program implements:

* FCFS
* SJF
* SRTF

  * FCFS tie breaker
  * High integer = high priority
  * Low integer = high priority
* Round Robin

## Results

For each algorithm, the program calculates:

* Average Arrival Time
* Average Completion Time
* Average Turnaround Time
* Throughput

It also generates Gantt charts to show how the processes are scheduled.

## Technologies Used

* Python
* Flask
* Pandas
* OpenPyXL
* Plotly
* HTML/CSS/JavaScript

## How to Run

Install the required packages:


pip install -r requirements.txt


Run the program:

python cpu_scheduler.py

Then open:


http://127.0.0.1:5000


The program can also generate an Excel file containing 1,500 randomized processes.

## Author
Joy Gatimu

