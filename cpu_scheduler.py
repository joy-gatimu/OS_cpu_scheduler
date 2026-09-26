from flask import Flask, request, render_template_string, send_file
import pandas as pd
import random
import os
import json
from collections import deque

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
GENERATED_FOLDER = "generated"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)


# ============================================================
# PROCESS CLASS
# ============================================================


class Process:

    def __init__(self, pid, arrival, burst, priority, order):

        self.pid = str(pid)
        self.arrival = int(arrival)
        self.burst = int(burst)
        self.priority = int(priority)

        self.order = order

        self.remaining = self.burst

        self.completion = 0
        self.turnaround = 0


# ============================================================
# GENERATE 1500 RANDOM PROCESSES
# ============================================================


def generate_excel():

    data = []

    for i in range(1, 1501):

        arrival_time = random.randint(0, 1000)

        burst_time = random.randint(1, 50)

        priority = random.randint(1, 10)

        data.append(
            {
                "Process": f"P{i}",
                "Arrival Time": arrival_time,
                "Burst Time": burst_time,
                "Priority": priority,
            }
        )

    df = pd.DataFrame(data)

    file_path = os.path.join(GENERATED_FOLDER, "processes_1500.xlsx")

    df.to_excel(file_path, index=False)

    return file_path


# ============================================================
# READ AND VALIDATE EXCEL FILE
# ============================================================


def read_excel(file_path):

    df = pd.read_excel(file_path)

    required_columns = ["Process", "Arrival Time", "Burst Time", "Priority"]

    missing = [column for column in required_columns if column not in df.columns]

    if missing:

        raise ValueError("Missing columns: " + ", ".join(missing))

    if len(df) != 1500:

        raise ValueError(
            "The Excel file must contain exactly "
            f"1500 processes. Your file contains {len(df)}."
        )

    processes = []

    for index, row in df.iterrows():

        try:

            arrival = int(row["Arrival Time"])

            burst = int(row["Burst Time"])

            priority = int(row["Priority"])

        except Exception:

            raise ValueError(f"Invalid numerical value in row {index + 2}.")

        if arrival < 0:

            raise ValueError("Arrival Time cannot be negative.")

        if burst <= 0:

            raise ValueError("Burst Time must be greater than 0.")

        processes.append(Process(row["Process"], arrival, burst, priority, index))

    return processes


# ============================================================
# COPY PROCESSES
# ============================================================


def copy_processes(original):

    return [Process(p.pid, p.arrival, p.burst, p.priority, p.order) for p in original]


# ============================================================
# MERGE GANTT SEGMENTS
# ============================================================


def merge_gantt(gantt):

    if not gantt:

        return []

    merged = [gantt[0]]

    for current in gantt[1:]:

        previous = merged[-1]

        if previous[0] == current[0] and previous[2] == current[1]:

            merged[-1] = (previous[0], previous[1], current[2])

        else:

            merged.append(current)

    return merged


# ============================================================
# FCFS
# ============================================================


def fcfs(original):

    processes = copy_processes(original)

    processes.sort(key=lambda p: (p.arrival, p.order))

    time = 0

    gantt = []

    for process in processes:

        if time < process.arrival:

            gantt.append(("Idle", time, process.arrival))

            time = process.arrival

        start = time

        time += process.burst

        process.completion = time

        gantt.append((process.pid, start, time))

    return processes, merge_gantt(gantt)


# ============================================================
# SJF - NON PREEMPTIVE
# ============================================================


def sjf(original):

    processes = copy_processes(original)

    remaining = processes.copy()

    time = 0

    gantt = []

    while remaining:

        ready = [p for p in remaining if p.arrival <= time]

        if not ready:

            next_process = min(remaining, key=lambda p: (p.arrival, p.order))

            gantt.append(("Idle", time, next_process.arrival))

            time = next_process.arrival

            continue

        process = min(ready, key=lambda p: (p.burst, p.arrival, p.order))

        remaining.remove(process)

        start = time

        time += process.burst

        process.completion = time

        gantt.append((process.pid, start, time))

    return processes, merge_gantt(gantt)


# ============================================================
# SRTF
#
# TIE BREAKERS:
#
# 1. FCFS
# 2. High Integer = High Priority
# 3. Low Integer = High Priority
# ============================================================


def srtf(original, tie_breaker):
    processes = copy_processes(original)

    # Sort processes by arrival time first
    processes.sort(key=lambda p: (p.arrival, p.order))

    import heapq

    n = len(processes)
    index = 0
    completed = 0
    time = 0

    # Priority queue for ready processes
    ready = []

    # Gantt chart
    gantt = []

    current_pid = None
    current_start = None

    # --------------------------------------------------------
    # DEFINE THE TIE-BREAKING RULE
    # --------------------------------------------------------
    def priority_key(p):

        # SRTF + FCFS tie breaker
        if tie_breaker == "FCFS":
            return (
                p.remaining,
                p.arrival,
                p.order,
                p.order
            )

        # SRTF + High Integer = High Priority
        elif tie_breaker == "High Integer = High Priority":
            return (
                p.remaining,
                -p.priority,
                p.arrival,
                p.order
            )

        # SRTF + Low Integer = High Priority
        else:
            return (
                p.remaining,
                p.priority,
                p.arrival,
                p.order
            )

    # --------------------------------------------------------
    # MAIN SRTF LOOP
    # --------------------------------------------------------
    while completed < n:

        # ----------------------------------------------------
        # IF CPU IS IDLE, MOVE TIME TO NEXT ARRIVING PROCESS
        # ----------------------------------------------------
        if not ready and index < n and time < processes[index].arrival:

            if current_pid is not None:
                gantt.append(
                    (current_pid, current_start, time)
                )

                current_pid = None
                current_start = None

            gantt.append(
                ("Idle", time, processes[index].arrival)
            )

            time = processes[index].arrival

        # ----------------------------------------------------
        # ADD ALL PROCESSES THAT HAVE ARRIVED
        # ----------------------------------------------------
        while index < n and processes[index].arrival <= time:

            p = processes[index]

            heapq.heappush(
                ready,
                (*priority_key(p), p)
            )

            index += 1

        # ----------------------------------------------------
        # IF NOTHING IS READY, CONTINUE
        # ----------------------------------------------------
        if not ready:
            continue

        # ----------------------------------------------------
        # SELECT PROCESS ACCORDING TO SRTF + TIE BREAKER
        # ----------------------------------------------------
        _, _, _, _, process = heapq.heappop(ready)

        # ----------------------------------------------------
        # START A NEW GANTT SEGMENT IF PROCESS CHANGES
        # ----------------------------------------------------
        if current_pid != process.pid:

            if current_pid is not None:
                gantt.append(
                    (current_pid, current_start, time)
                )

            current_pid = process.pid
            current_start = time

        # ----------------------------------------------------
        # FIND WHEN CURRENT PROCESS WOULD FINISH
        # ----------------------------------------------------
        finish_time = time + process.remaining

        # ----------------------------------------------------
        # CHECK IF ANOTHER PROCESS ARRIVES BEFORE COMPLETION
        # ----------------------------------------------------
        if index < n:

            next_arrival = processes[index].arrival

            run_until = min(
                finish_time,
                next_arrival
            )

        else:
            run_until = finish_time

        # ----------------------------------------------------
        # EXECUTE THE PROCESS
        # ----------------------------------------------------
        execution = run_until - time

        process.remaining -= execution

        time = run_until

        # ----------------------------------------------------
        # ADD ANY NEWLY ARRIVED PROCESSES
        # ----------------------------------------------------
        while index < n and processes[index].arrival <= time:

            p = processes[index]

            heapq.heappush(
                ready,
                (*priority_key(p), p)
            )

            index += 1

        # ----------------------------------------------------
        # PROCESS FINISHED
        # ----------------------------------------------------
        if process.remaining == 0:

            process.completion = time

            completed += 1

            gantt.append(
                (process.pid, current_start, time)
            )

            current_pid = None
            current_start = None

        # ----------------------------------------------------
        # PROCESS WAS PREEMPTED
        # ----------------------------------------------------
        else:

            heapq.heappush(
                ready,
                (*priority_key(process), process)
            )

            current_pid = process.pid

    return processes, merge_gantt(gantt)

# ============================================================
# ROUND ROBIN
# ============================================================


def round_robin(original, quantum):

    processes = copy_processes(original)

    processes.sort(key=lambda p: (p.arrival, p.order))

    queue = deque()

    time = 0

    index = 0

    gantt = []

    while index < len(processes) or queue:

        if not queue:

            if time < processes[index].arrival:

                gantt.append(("Idle", time, processes[index].arrival))

                time = processes[index].arrival

        while index < len(processes) and processes[index].arrival <= time:

            queue.append(processes[index])

            index += 1

        process = queue.popleft()

        start = time

        execution = min(quantum, process.remaining)

        process.remaining -= execution

        time += execution

        gantt.append((process.pid, start, time))

        while index < len(processes) and processes[index].arrival <= time:

            queue.append(processes[index])

            index += 1

        if process.remaining > 0:

            queue.append(process)

        else:

            process.completion = time

    return processes, merge_gantt(gantt)


# ============================================================
# CALCULATE METRICS
# ============================================================


def calculate_metrics(processes):

    for process in processes:

        process.turnaround = process.completion - process.arrival

    average_arrival = sum(p.arrival for p in processes) / len(processes)

    average_completion = sum(p.completion for p in processes) / len(processes)

    average_turnaround = sum(p.turnaround for p in processes) / len(processes)

    final_completion = max(p.completion for p in processes)

    throughput = len(processes) / final_completion

    return {
        "Average Arrival Time": round(average_arrival, 2),
        "Average Completion Time": round(average_completion, 2),
        "Average Turnaround Time": round(average_turnaround, 2),
        "Throughput": round(throughput, 4),
    }


# ============================================================
# RUN ALL ALGORITHMS
# ============================================================


def run_all_algorithms(original, quantum):

    results = []

    gantt_charts = {}

    # --------------------------------------------------------
    # FCFS
    # --------------------------------------------------------

    processes, gantt = fcfs(original)

    metrics = calculate_metrics(processes)

    results.append({"Algorithm": "FCFS", **metrics})

    gantt_charts["FCFS"] = gantt

    # --------------------------------------------------------
    # SJF
    # --------------------------------------------------------

    processes, gantt = sjf(original)

    metrics = calculate_metrics(processes)

    results.append({"Algorithm": "SJF", **metrics})

    gantt_charts["SJF"] = gantt

    # --------------------------------------------------------
    # SRTF - FCFS
    # --------------------------------------------------------

    processes, gantt = srtf(original, "FCFS")

    metrics = calculate_metrics(processes)

    results.append({"Algorithm": "SRTF - FCFS", **metrics})

    gantt_charts["SRTF - FCFS"] = gantt

    # --------------------------------------------------------
    # SRTF - HIGH INTEGER HIGH PRIORITY
    # --------------------------------------------------------

    processes, gantt = srtf(original, "High Integer = High Priority")

    metrics = calculate_metrics(processes)

    results.append({"Algorithm": "SRTF - High Integer = High Priority", **metrics})

    gantt_charts["SRTF - High Integer = High Priority"] = gantt

    # --------------------------------------------------------
    # SRTF - LOW INTEGER HIGH PRIORITY
    # --------------------------------------------------------

    processes, gantt = srtf(original, "Low Integer = High Priority")

    metrics = calculate_metrics(processes)

    results.append({"Algorithm": "SRTF - Low Integer = High Priority", **metrics})

    gantt_charts["SRTF - Low Integer = High Priority"] = gantt

    # --------------------------------------------------------
    # ROUND ROBIN
    # --------------------------------------------------------

    processes, gantt = round_robin(original, quantum)

    metrics = calculate_metrics(processes)

    results.append({"Algorithm": f"Round Robin (Q={quantum})", **metrics})

    gantt_charts["Round Robin"] = gantt

    return results, gantt_charts


# ============================================================
# HTML PAGE
# ============================================================

HTML = """<!DOCTYPE html>
<html>
<head>
    <title>CPU Scheduling Simulator</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #dff3ff;
            margin: 0;
            padding: 30px;
        }
        .container {
            max-width: 1400px;
            margin: auto;
        }
        h1 {
            text-align: center;
            color: #222;
            margin: 0;
        }
        h2 {
            color: #333;
        }
        .card {
            background: #ffffff;
            padding: 25px;
            margin-bottom: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .title-card {
            background: linear-gradient(135deg, #6bb6e8, #3f8fc7);
            text-align: center;
            padding: 30px 22px;
            margin-bottom: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 14px rgba(0, 60, 120, 0.25);
        }
        .title-card h1 {
            margin: 0;
            font-size: 34px;
            color: #ffffff;
            letter-spacing: 0.5px;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }
        input[type="file"] {
            padding: 10px;
        }
        input[type="number"] {
            padding: 10px;
            width: 100px;
        }
        button {
            padding: 10px 18px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
            background: #333;
            color: white;
        }
        button:hover {
            opacity: 0.8;
        }
        .chart-button {
            background: #555;
        }
        select {
            padding: 10px;
            font-size: 15px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: center;
        }
        th {
            background: #333;
            color: white;
        }
        tr:nth-child(even) {
            background: #f5f5f5;
        }
        .success {
            padding: 15px;
            background: #e8f5e9;
            border: 1px solid #a5d6a7;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .error {
            padding: 15px;
            background: #ffebee;
            border: 1px solid #ef9a9a;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .info {
            padding: 15px;
            background: #eeeeee;
            border-radius: 5px;
            margin-top: 15px;
        }
        #gantt {
            width: 100%;
            height: 450px;
        }
    </style>
</head>
<body>
<div class="container">
    <div class="card title-card">
        <h1>
            CPU Scheduling Simulator
        </h1>
    </div>
    <!-- ================================================= -->
    <!-- EXCEL GENERATOR -->
    <!-- ================================================= -->
    <div class="card">
        <h2>
            Step 1: Generate 1500 Processes
        </h2>
        <p>
            Click the button below to generate an Excel
            file containing exactly 1,500 randomized processes.
        </p>
        <form action="/generate" method="get">
            <button type="submit">
                Generate 1500-Process Excel File
            </button>
        </form>
    </div>
    <!-- ================================================= -->
    <!-- UPLOAD -->
    <!-- ================================================= -->
    <div class="card">
        <h2>
            Step 2: Upload Excel File
        </h2>
        <p>
            Upload an Excel file containing:
        </p>
        <ul>
            <li>Process</li>
            <li>Arrival Time</li>
            <li>Burst Time</li>
            <li>Priority</li>
        </ul>
        <p>
            The file must contain exactly 1,500 processes.
        </p>
        <form
            action="/simulate"
            method="post"
            enctype="multipart/form-data"
        >
            <input
                type="file"
                name="file"
                accept=".xlsx,.xls"
                required
            >
            <br><br>
            <label>
                <strong>
                    Round Robin Quantum:
                </strong>
            </label>
            <input
                type="number"
                name="quantum"
                value="4"
                min="1"
                required
            >
            <br><br>
            <button type="submit">
                Run CPU Scheduling Algorithms
            </button>
        </form>
    </div>
    {% if error %}
        <div class="error">
            <strong>
                Error:
            </strong>
            {{ error }}
        </div>
    {% endif %}
    {% if results %}
        <!-- ================================================= -->
        <!-- RESULTS TABLE -->
        <!-- ================================================= -->
        <div class="card">
            <h2>
                Scheduling Results
            </h2>
            <div class="success">
                The Excel file was successfully processed.
                <br><br>
                All required CPU scheduling algorithms
                have been executed.
            </div>
            <table>
                <thead>
                    <tr>
                        <th>
                            Algorithm
                        </th>
                        <th>
                            Average Arrival Time
                        </th>
                        <th>
                            Average Completion Time
                        </th>
                        <th>
                            Average Turnaround Time
                        </th>
                        <th>
                            Throughput
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in results %}
                    <tr>
                        <td>
                            <strong>
                                {{ row["Algorithm"] }}
                            </strong>
                        </td>
                        <td>
                            {{ row["Average Arrival Time"] }}
                        </td>
                        <td>
                            {{ row["Average Completion Time"] }}
                        </td>
                        <td>
                            {{ row["Average Turnaround Time"] }}
                        </td>
                        <td>
                            {{ row["Throughput"] }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <!-- ================================================= -->
        <!-- GANTT CHART -->
        <!-- ================================================= -->
        <div class="card">
            <h2>
                Gantt Charts
            </h2>
            <p>
                Select an algorithm below to display
                its Gantt chart.
            </p>
            <p>
                Because the input contains 1,500 processes,
                the chart uses a single horizontal CPU timeline.
                You can zoom, hover over segments, and use
                the range slider.
            </p>
            <!-- ALGORITHM BUTTONS -->
            <div>
                {% for algorithm in gantt_charts.keys() %}
                    <button
                        class="chart-button"
                        onclick="showChart('{{ algorithm }}')"
                    >
                        {{ algorithm }}
                    </button>
                {% endfor %}
            </div>
            <br>
            <!-- DISPLAY LIMIT -->
            <label>
                <strong>
                    Number of Gantt segments to display:
                </strong>
            </label>
            <select
                id="processLimit"
                onchange="updateChart()"
            >
                <option value="50">
                    First 50
                </option>
                <option
                    value="100"
                    selected
                >
                    First 100
                </option>
                <option value="250">
                    First 250
                </option>
                <option value="500">
                    First 500
                </option>
                <option value="1000">
                    First 1000
                </option>
                <option value="1500">
                    First 1500
                </option>
                <option value="999999">
                    All
                </option>
            </select>
            <br><br>
            <!-- GANTT CHART -->
            <div id="gantt"></div>
        </div>
        <!-- ================================================= -->
        <!-- GANTT JAVASCRIPT -->
        <!-- ================================================= -->
        <script>
            const allGantt =
                {{ gantt_json | safe }};
            let currentAlgorithm = null;
            // ------------------------------------------------
            // SHOW SELECTED ALGORITHM
            // ------------------------------------------------
            function showChart(algorithm) {
                currentAlgorithm = algorithm;
                updateChart();
            }
            // ------------------------------------------------
            // UPDATE CHART
            // ------------------------------------------------
            function updateChart() {
                if (currentAlgorithm === null) {
                    const algorithms =
                        Object.keys(allGantt);
                    if (algorithms.length === 0) {
                        return;
                    }
                    currentAlgorithm =
                        algorithms[0];
                }
                const ganttData =
                    allGantt[currentAlgorithm];
                const limit =
                    parseInt(
                        document
                            .getElementById("processLimit")
                            .value
                    );
                const selectedData =
                    ganttData.slice(0, limit);
                const traces = [];
                selectedData.forEach(function(item) {
                    // ----------------------------------------
                    // IDLE CPU
                    // ----------------------------------------
                    if (item.pid === "Idle") {
                        traces.push({
                            x: [
                                item.start,
                                item.end
                            ],
                            y: [
                                "CPU",
                                "CPU"
                            ],
                            mode: "lines",
                            line: {
                                width: 35,
                                dash: "dot"
                            },
                            hovertemplate:
                                "<b>CPU IDLE</b>" +
                                "<br>Start: " +
                                item.start +
                                "<br>End: " +
                                item.end +
                                "<br>Duration: " +
                                (
                                    item.end
                                    - item.start
                                ) +
                                "<extra></extra>"
                        });
                    }
                    // ----------------------------------------
                    // PROCESS
                    // ----------------------------------------
                    else {
                        traces.push({
                            x: [
                                item.start,
                                item.end
                            ],
                            y: [
                                "CPU",
                                "CPU"
                            ],
                            mode: "lines",
                            line: {
                                width: 35
                            },
                            name: item.pid,
                            hovertemplate:
                                "<b>" +
                                item.pid +
                                "</b>" +
                                "<br>Start: " +
                                item.start +
                                "<br>End: " +
                                item.end +
                                "<br>Duration: " +
                                (
                                    item.end
                                    - item.start
                                ) +
                                "<extra></extra>"
                        });
                    }
                });
                // --------------------------------------------
                // DRAW PLOT
                // --------------------------------------------
                Plotly.newPlot(
                    "gantt",
                    traces,
                    {
                        title:
                            currentAlgorithm +
                            " Gantt Chart",
                        xaxis: {
                            title:
                                "CPU Time",
                            rangeslider: {
                                visible: true
                            },
                            fixedrange: false
                        },
                        yaxis: {
                            title:
                                "CPU",
                            showticklabels: true,
                            fixedrange: true
                        },
                        height: 450,
                        showlegend: false,
                        hovermode:
                            "closest",
                        margin: {
                            l: 80,
                            r: 30,
                            t: 70,
                            b: 100
                        }
                    },
                    {
                        responsive: true,
                        scrollZoom: true
                    }
                );
            }
            // ------------------------------------------------
            // DISPLAY FIRST CHART AUTOMATICALLY
            // ------------------------------------------------
            window.onload = function() {
                const algorithms =
                    Object.keys(allGantt);
                if (algorithms.length > 0) {
                    currentAlgorithm =
                        algorithms[0];
                    updateChart();
                }
            };
        </script>
    {% endif %}
</div>
</body>
</html>"""


# ============================================================
# HOME PAGE
# ============================================================


@app.route("/", methods=["GET"])
def home():

    return render_template_string(HTML)


# ============================================================
# GENERATE EXCEL
# ============================================================


@app.route("/generate", methods=["GET"])
def generate():

    file_path = generate_excel()

    return send_file(file_path, as_attachment=True, download_name="processes_1500.xlsx")


# ============================================================
# SIMULATE
# ============================================================


@app.route("/simulate", methods=["POST"])
def simulate():

    try:

        # ----------------------------------------------------
        # CHECK FILE
        # ----------------------------------------------------

        if "file" not in request.files:

            raise ValueError("No Excel file was uploaded.")

        file = request.files["file"]

        if file.filename == "":

            raise ValueError("Please select an Excel file.")

        # ----------------------------------------------------
        # CHECK FILE TYPE
        # ----------------------------------------------------

        if not (
            file.filename.lower().endswith(".xlsx")
            or file.filename.lower().endswith(".xls")
        ):

            raise ValueError("Please upload an Excel file (.xlsx or .xls).")

        # ----------------------------------------------------
        # SAVE UPLOAD
        # ----------------------------------------------------

        file_path = os.path.join(UPLOAD_FOLDER, file.filename)

        file.save(file_path)

        # ----------------------------------------------------
        # READ EXCEL
        # ----------------------------------------------------

        processes = read_excel(file_path)

        # ----------------------------------------------------
        # GET ROUND ROBIN QUANTUM
        # ----------------------------------------------------

        quantum = int(request.form.get("quantum", 4))

        if quantum <= 0:

            raise ValueError("Round Robin quantum must be greater than 0.")

        # ----------------------------------------------------
        # RUN ALGORITHMS
        # ----------------------------------------------------

        results, gantt_charts = run_all_algorithms(processes, quantum)

        # ----------------------------------------------------
        # CONVERT GANTT DATA TO JSON
        # ----------------------------------------------------

        gantt_json_data = {}

        for algorithm, gantt in gantt_charts.items():

            gantt_json_data[algorithm] = [
                {"pid": segment[0], "start": segment[1], "end": segment[2]}
                for segment in gantt
            ]

        gantt_json = json.dumps(gantt_json_data)

        # ----------------------------------------------------
        # DISPLAY RESULTS
        # ----------------------------------------------------

        return render_template_string(
            HTML,
            results=results,
            gantt_charts=gantt_charts,
            gantt_json=gantt_json,
            error=None,
        )

    except Exception as e:

        return render_template_string(
            HTML, results=None, gantt_charts={}, gantt_json="{}", error=str(e)
        )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("CPU SCHEDULING SIMULATOR")
    print("=" * 60)
    print()
    print("Server starting...")
    print("Open http://127.0.0.1:5000 in your browser.")
    print("Press CTRL+C to stop the program.")
    print()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=False)
