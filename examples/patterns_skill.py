#!/usr/bin/env python3
# ========================================
# Copyright 2021 22nd Solutions, LLC
# Copyright 2024 Martin TOUZOT
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
# USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# ========================================
"""Patterns Heykube solver.

The script helps the Heykube player to solve the cube with different patterns.

Please note that to connect the cube, it must be solved.

Usage:
    python3 patterns_skill.py
"""
import heykube
import random

# Connect to the cube
cube = heykube.heykube()
device = cube.get_device()

# If not found, just exit
if device is None:
    exit()

# Run the connection
if not cube.connect(device):
    print("Failed to connect with a HEYKUBE")
    exit()

# Reinitialize the cube
while not cube.is_solved():
    print("Cube not solved - please solve the cube first")
    cube.disconnect()
    exit()

# ----------------------------------------------------
# Run the main loop, and catch keyboard exceptions
# also triggers disconnect at the end
# ---------------------------------------------------
try:
    # Turn on the notifications
    cube.enable_notifications(["instruction_empty", "instruction_max"])

    # Get the list of pattern names
    pattern_names = cube.get_pattern_names()

    while True:
        # ------------------------------------------------------
        # Pick the pattern
        # ------------------------------------------------------
        choice = None
        list_index = 0
        while not choice:
            print("\n\nHere are the patterns available in HEYKUBE:")
            for loop1 in range(len(pattern_names) // 4):
                out_text = "    "
                for loop2 in range(4):
                    out_text += "{:16} ".format(pattern_names[loop1])
                print(out_text)
            response = input("\nPick a pattern name or select [random]?: ")

            # Handle the selection
            if "random" in response or response == "":
                random_index = random.randrange(0, len(pattern_names))
                choice = pattern_names[random_index]
            elif response in pattern_names:
                choice = response
        print("")

        # ------------------------------------------------------
        # Enable te the instructions
        # ------------------------------------------------------

        # Enable the pattern
        cube.enable_pattern(choice)

        # Instructions
        print(f"Follow the hints on the HEYKUBE faces to solve for {choice}")

        # Simulate the users
        pattern_moves = cube.read_instructions()
        print(f"Pattern for {choice}: {pattern_moves}")

        # Builds a simulation of the pattern to print to the screen
        sim_cube = heykube.Cube()
        sim_cube.apply_moves(pattern_moves)
        print(sim_cube)

        # --------------------------------------------------
        # Wait for the pattern
        # --------------------------------------------------
        done = False

        # Clear any notifications
        cube.clear_notify()
        seq_num = cube.get_seq_num()

        while True:
            # Wait for notification
            num_moves, cube_status = cube.wait_for_notify()
            print(f"num_moves = {num_moves}, cube_state = {cube_status}")

            # Check notifications
            if "instruction_empty" in cube_status:
                # Play sound and light the LEDs
                print("You solved the pattern!")
                cube.print_cube()
                seq_num = cube_status["seq_num"]
                break
            elif "instruction_max" in cube_status:
                print("It seems like you are ignoring patterns")
                done = True
                break
            else:
                new_moves = cube.read_moves(seq_num)
                seq_num = new_moves["seq_num"]
                print(f'New moves: {new_moves["moves"]}')

        # Exit early
        if done:
            break

        # --------------------------------------------------------------
        # Get back to solved state
        # --------------------------------------------------------------
        print(
            """\nFollow the instructions on the cube"""
            """to get back to the solved state"""
        )

        # Undo to the pattern
        reverse_moves = cube.read_instructions()
        print(f"Reverse pattern: {pattern_moves}")

        # wait for user
        while True:
            # Wait for notification
            num_moves, cube_status = cube.wait_for_notify(timeout=10)

            # Check notifications
            if "instruction_empty" in cube_status:
                # Play sound and light the LEDs
                print("You are back to the solved state!")
                cube.print_cube()
                break
            elif "instruction_max" in cube_status:
                print("It seems like you are ignoring patterns - exiting")
                done = True
                break
            else:
                new_moves = cube.read_moves(seq_num)
                seq_num = new_moves["seq_num"]
                print(f"New moves: {new_moves['moves']}")

        # Exit early
        if done:
            break

# Handling exceptions and breakout
except KeyboardInterrupt:
    print("Exiting after Ctrl-c")
except Exception as e:
    print(f"Trapping exception {e}")
finally:
    cube.disconnect()
