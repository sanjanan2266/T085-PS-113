"""
Command Line Interface for PS-113 School Fee Management Engine
Supports command files, interactive mode, and sample workflow demonstration.
"""
import argparse
import sys
from pathlib import Path
from engine.command_processor import CommandProcessor


def main():
    parser = argparse.ArgumentParser(
        description="PS-113: School Fee Management Engine (K-12 School Administration)"
    )
    parser.add_argument(
        "command_file",
        nargs="?",
        help="Path to command file (*.txt or *.commands) to execute sequentially",
    )
    parser.add_argument(
        "--run-sample",
        action="store_true",
        help="Execute the full sample dataset workflow and print audit summary",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive command prompt",
    )

    args = parser.parse_args()
    processor = CommandProcessor()

    if args.run_sample:
        sample_cmd = Path("sample_data") / "commands.txt"
        if not sample_cmd.exists():
            print(f"Sample command file not found at {sample_cmd}. Please generate sample data first.")
            sys.exit(1)
        print(f"=== Running Sample Dataset Workflow ({sample_cmd}) ===")
        logs = processor.process_file(sample_cmd)
        for log in logs:
            print(log)
        return

    if args.command_file:
        cmd_path = Path(args.command_file)
        if not cmd_path.exists():
            print(f"Error: Command file not found: {cmd_path}", file=sys.stderr)
            sys.exit(1)
        logs = processor.process_file(cmd_path)
        for log in logs:
            print(log)
        return

    if args.interactive:
        print("=== School Fee Engine Interactive Shell ===")
        print("Type commands (e.g. PRINT_DEFAULTERS 2026-10-15) or 'exit' to quit.")
        while True:
            try:
                line = input("fee-engine> ").strip()
                if not line:
                    continue
                if line.lower() in ["exit", "quit", "q"]:
                    break
                out = processor.process_command(line)
                if out:
                    print(out)
            except (KeyboardInterrupt, EOFError):
                break
        return

    # If no arguments provided, show help
    parser.print_help()


if __name__ == "__main__":
    main()
