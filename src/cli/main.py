import argparse
import datetime
import json
import logging
import traceback
import urllib.request
from collections import defaultdict
from typing import Any, Dict, List

__version__ = "0.0.1"

__doc__ = """
This script processes healthcare export data by fetching and analyzing event data 
associated with a specified export ID. It retrieves data from a local API, aggregates 
event counts per patient and event type, and outputs the results in JSON format.

Usage:
    Run the script with one of the available export IDs ("demo", "small", "large") 
    as a command-line argument to process the corresponding dataset.

Examples:
    uv run cli -e demo
    uv run cli -e small -o small.json
    uv run cli -e large -o large.json --verbose
    
Features:
- Fetches export metadata and associated download IDs from a local API.
- Processes event data for each download, aggregating counts by patient and event type.
- Outputs the aggregated data in a structured JSON format.

Dependencies:
- Requires the `argparse`, `json`, `urllib.request`, and `collections` modules.

Note:
- The script assumes the API is running locally at "http://localhost:8000/api".
- Malformed rows in the data are skipped during processing.
"""


def get_opts() -> argparse.Namespace:
    """Return an argparse object."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-d",
        "--verbose",
        default=logging.INFO,
        action="store_const",
        const=logging.DEBUG,
        help="enable debug logging",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
        help="show version and exit",
    )
    parser.add_argument(
        "-t", "--time", dest="time", action="store_true", help="include execution time"
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output file name (default: None)",
    )
    parser.add_argument(
        "-e",
        "--export_id",
        choices=["demo", "small", "large"],
        default="demo",
        help="ID of the export to process; supported IDs: demo, small, large (default: demo)",
    )

    args: argparse.Namespace = parser.parse_args()
    logging.basicConfig(level=args.verbose)
    return args


def process_data(export_id: str, output_file: str | None) -> None:
    """
    Processes data for a given export ID by fetching and aggregating event data
    from a remote API, and optionally writes the results to an output file.
    Args:
        export_id (str): The unique identifier for the export to process.
        output_file (str | None): The path to the file where the output JSON
            should be written. If None, the output is printed to the console.
    Returns:
        None
    The function performs the following steps:
    1. Fetches export details from the API, including a list of download IDs.
    2. Iterates through each download ID, fetching and processing event data.
    3. Aggregates event counts per patient and totals across all patients.
    4. Outputs the aggregated data as a JSON object, either to the console or
       to the specified output file.
    The output JSON structure includes:
    - "patients": A dictionary where each key is a patient ID and the value is
      another dictionary mapping event types to their respective counts.
    - "totals": A dictionary mapping event types to their total counts across
      all patients.
    Notes:
        - The function skips malformed rows in the event data.
        - The API base URL is hardcoded as "http://localhost:8000/api".
        - Debug-level logging is used to trace the processing steps.
    Raises:
        urllib.error.URLError: If there is an issue connecting to the API.
        json.JSONDecodeError: If the API response contains invalid JSON.
        KeyError: If the expected keys are missing in the API response.
    """

    logging.debug(f"Starting to process export {export_id}")
    base_url: str = "http://localhost:8000/api"

    # Discover downloads
    export_url: str = f"{base_url}/export/{export_id}"
    logging.debug(f"Fetching export details from {export_url}")
    with urllib.request.urlopen(export_url) as response:
        export_data: Dict[str, Any] = json.loads(response.read().decode("utf-8"))[
            "data"
        ]
    download_ids: List[str] = export_data["download_ids"]
    logging.debug(f"Found {len(download_ids)} downloads for export {export_id}")

    # Initialize counters
    patient_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    total_counts: Dict[str, int] = defaultdict(int)

    # Process each download
    for download_id in download_ids:
        logging.debug(
            f"Processing download ID {download_id} ({download_ids.index(download_id) + 1} of {len(download_ids)})"
        )
        data_url: str = f"{base_url}/export/{export_id}/{download_id}/data"
        with urllib.request.urlopen(data_url) as response:
            # Skip header
            response.readline()
            row_count: int = 0
            for line in response:
                line_str: str = line.decode("utf-8").strip()
                if not line_str:
                    continue
                row: List[str] = line_str.split(",")
                if len(row) != 4:
                    logging.debug(f"Skipping malformed row: {line_str}")
                    continue  # skip malformed rows
                patient_id: str
                event_time: str
                event_type: str
                value: str
                patient_id, event_time, event_type, value = row
                patient_counts[patient_id][event_type] += 1
                total_counts[event_type] += 1
                row_count += 1
            logging.debug(f"Processed {row_count} rows for download {download_id}")

    logging.debug(
        f"Finished processing all downloads. Total patients: {len(patient_counts)}, total events: {sum(total_counts.values())}"
    )

    # Prepare output JSON
    logging.debug("Preparing output JSON")
    output: Dict[str, Dict[str, Any]] = {
        "patients": dict(patient_counts),
        "totals": dict(total_counts),
    }

    # Convert defaultdict to dict for JSON serialization
    for patient in output["patients"]:
        output["patients"][patient] = dict(output["patients"][patient])

    print(json.dumps(output, indent=2))
    if output_file:
        logging.debug(f"Writing output to {output_file}")
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)


def main() -> int:
    """
    The main entry point for the script.
    This function parses command-line arguments, processes data based on the
    provided options, and logs the execution time if requested. It handles
    exceptions and logs errors if any occur during execution.
    Returns:
        int: Returns 0 on successful execution, or 255 if an error occurs.
    """

    try:
        opts: argparse.Namespace = get_opts()
        if opts.time:
            start: datetime.datetime = datetime.datetime.now()

        process_data(opts.export_id, opts.output)

        if opts.time:
            end: datetime.datetime = datetime.datetime.now()
            logging.info(f"script completed in: {end - start}")
        return 0
    except Exception as err:
        logging.error(err)
        traceback.print_exc()
        return 255
