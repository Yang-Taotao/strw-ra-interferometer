"""
Main exec.

Example CLI:
    // for observation runs
    python main.py
    // for testing osmocom_source fake hackrf data processing
    python main.py -t
    python main.py -t --duration 10 --rate 1000000
    // for purging generated test data
    python main.py -p -y
"""

from raifm.cli import main

if __name__ == "__main__":
    main()
