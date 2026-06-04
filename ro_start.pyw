"""Launcher silencioso do RO Bot."""

import os
import subprocess
import sys


os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "ro_bot.py"], check=False)
