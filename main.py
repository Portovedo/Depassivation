import tkinter as tk
import argparse
from gui import DepassivationApp

if __name__ == "__main__":
    # Set up an argument parser to detect if we want to run in simulation mode
    parser = argparse.ArgumentParser(
        description="Run the Depassivation Station GUI."
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run the application in simulation mode without connecting to hardware."
    )
    args = parser.parse_args()

    # Start the main Tkinter application
    root = tk.Tk()
    # Pass the 'simulate' flag to the application's constructor
    app = DepassivationApp(root, simulate=args.simulate)
    root.mainloop()
