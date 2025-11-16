import json
import logging
import sys
from unittest.mock import Mock

import pytest

from cli.main import get_opts, process_data


class TestGetOpts:
    def test_get_opts_default(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli"])
        opts = get_opts()
        assert opts.export_id == "demo"
        assert opts.output is None
        assert opts.time is False
        assert opts.verbose == logging.INFO

    def test_get_opts_with_args(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["cli", "-e", "small", "-o", "out.json", "--verbose", "--time"]
        )
        opts = get_opts()
        assert opts.export_id == "small"
        assert opts.output == "out.json"
        assert opts.time is True
        assert opts.verbose == logging.DEBUG

    def test_get_opts_version(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["cli", "--version"])
        with pytest.raises(SystemExit):
            get_opts()
        captured = capsys.readouterr()
        assert "0.0.1" in captured.out


class TestProcessData:
    def test_process_data_basic(self, capsys, mocker):
        # Mock the export API response
        mock_export_response = Mock()
        mock_export_response.read.return_value = (
            b'{"data": {"download_ids": ["test-id"]}}'
        )
        mock_export_response.__enter__ = Mock(return_value=mock_export_response)
        mock_export_response.__exit__ = Mock(return_value=None)

        # Mock the data API response
        mock_data_response = Mock()
        mock_data_response.readline.return_value = (
            b"patient_id,event_time,event_type,value\n"
        )
        mock_data_response.__iter__ = Mock(
            return_value=iter([b"P001,2023-01-01T00:00:00Z,heart_rate,75\n"])
        )
        mock_data_response.__enter__ = Mock(return_value=mock_data_response)
        mock_data_response.__exit__ = Mock(return_value=None)

        # Mock urlopen to return the responses in order
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=[mock_export_response, mock_data_response],
        )

        # Call process_data
        process_data("demo", None)

        # Check the output
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "patients" in output
        assert "totals" in output
        assert output["patients"]["P001"]["heart_rate"] == 1
        assert output["totals"]["heart_rate"] == 1

    def test_process_data_with_output_file(self, tmp_path, mocker):
        # Mock the export API response
        mock_export_response = Mock()
        mock_export_response.read.return_value = (
            b'{"data": {"download_ids": ["test-id"]}}'
        )
        mock_export_response.__enter__ = Mock(return_value=mock_export_response)
        mock_export_response.__exit__ = Mock(return_value=None)

        # Mock the data API response
        mock_data_response = Mock()
        mock_data_response.readline.return_value = (
            b"patient_id,event_time,event_type,value\n"
        )
        mock_data_response.__iter__ = Mock(
            return_value=iter([b"P001,2023-01-01T00:00:00Z,heart_rate,75\n"])
        )
        mock_data_response.__enter__ = Mock(return_value=mock_data_response)
        mock_data_response.__exit__ = Mock(return_value=None)

        # Mock urlopen
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=[mock_export_response, mock_data_response],
        )

        # Mock open for writing file
        output_file = tmp_path / "test_output.json"
        mock_open = mocker.patch("builtins.open", mocker.mock_open())

        # Call process_data
        process_data("demo", str(output_file))

        # Check that open was called for writing
        mock_open.assert_called_with(str(output_file), "w")

    def test_process_data_malformed_row(self, capsys, mocker):
        # Mock the export API response
        mock_export_response = Mock()
        mock_export_response.read.return_value = (
            b'{"data": {"download_ids": ["test-id"]}}'
        )
        mock_export_response.__enter__ = Mock(return_value=mock_export_response)
        mock_export_response.__exit__ = Mock(return_value=None)

        # Mock the data API response with malformed row
        mock_data_response = Mock()
        mock_data_response.readline.return_value = (
            b"patient_id,event_time,event_type,value\n"
        )
        mock_data_response.__iter__ = Mock(
            return_value=iter(
                [
                    b"P001,2023-01-01T00:00:00Z,heart_rate,75\n",
                    b"malformed,row\n",  # malformed
                    b"P002,2023-01-01T00:00:00Z,spo2,98\n",
                ]
            )
        )
        mock_data_response.__enter__ = Mock(return_value=mock_data_response)
        mock_data_response.__exit__ = Mock(return_value=None)

        # Mock urlopen
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=[mock_export_response, mock_data_response],
        )

        # Call process_data
        process_data("demo", None)

        # Check the output (should skip malformed row)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["patients"]["P001"]["heart_rate"] == 1
        assert output["patients"]["P002"]["spo2"] == 1
        assert output["totals"]["heart_rate"] == 1
        assert output["totals"]["spo2"] == 1
