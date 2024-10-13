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
"""Defines the HEYKUBE hardware internal structure."""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Tuple, Union, Optional, Any
from bleak.backends.device import BLEDevice
from heykube import heykube_btle
import time
import random
import logging

HKStatus = Dict[str, Union[bool, int]]

# -------------------------------------------------
# -------------------------------------------------
# Setup Logging capability
# -------------------------------------------------
# -------------------------------------------------
logging.basicConfig()
logger = logging.getLogger("heykube")


# --------------------------------------------------------
# Match class - helps to compare cube state with patterns
# --------------------------------------------------------
class Match:
    """
    Define the Match class.

    Enable HEYKUBE to match with patterns, and provide a notification.
    """

    def __init__(self, init_set: Optional[Union[Cube, str]] = None) -> None:
        """Match class constructor.

        :param init_set: The initial state of the match, either a Cube object
                         or a string representing the cube state.
        :type init_set: Cube or str, optional

        :ivar iter_index: The index used for iteration.
        :vartype iter_index: int
        :ivar match_state: The state of the match, represented as a list of
                           Cube_Color values, initialized to DontCare.
        :vartype match_state: list
        :returns: None
        :rtype: NoneType
        """
        # helps iterator
        self.iter_index = 0

        # setup the don't care
        self.match_state = [Cube_Color.DontCare] * 54
        self.clear()

        # initialize
        if init_set:
            if isinstance(init_set, Cube):
                for loop1 in range(54):
                    state = init_set.state[loop1] // 9
                    self.match_state[loop1] = Cube_Color(state)
            elif isinstance(init_set, str):
                if len(init_set) == 1:
                    self.add_face(init_set)
                else:
                    self.add_cubie(init_set)

    # -------------------------------------------------------
    # Basic operators
    # -------------------------------------------------------
    def decode_state(self, data: bytearray) -> None:
        """Decode the current state of the cube.

        Process a byte array to update the cube's state based on the encoded
        color information. The color values are extracted for each face of
        the cube using bit manipulation, with special handling for the center
        pieces of each face (which are fixed and not encoded).

        :param data: A byte array representing the encoded cube state.
        :type data: bytes
        :returns: None
        :rtype: NoneType
        """
        ptr = 0
        bit_pos = 0

        # go through all the faces
        for loop1 in range(54):
            if (loop1 % 9) == 4:
                # center of the face; assign fixed color
                self.match_state[loop1] = Cube_Color(loop1 // 9)
            else:
                # update bits to extract the color index
                color_index = (data[ptr] >> bit_pos) & 0x7

                # handle bit overflow cases
                if bit_pos == 6:
                    color_index |= (data[ptr + 1] & 0x1) << 2
                elif bit_pos == 7:
                    color_index |= (data[ptr + 1] & 0x3) << 1

                # assign the decoded color to the current face position
                self.matchState[loop1] = Cube_Color(color_index)

                # move to the next set of bits
                bit_pos += 3
                if bit_pos >= 8:
                    bit_pos -= 8
                    ptr += 1

    def encode_state(self) -> List[int]:
        """Encode the current state of the cube.

        Encode the state of the cube into a list of integers (bytearray).
        Processe each non-center piece on each face of the cube, applying bit
        manipulation to pack the cube colors into the list.

        :returns: A list of integers representing the encoded cube state.
        :rtype: List[int]
        """
        cstate = [0] * 18
        ptr = 0
        bit_pos = 0
        for loop1 in range(54):
            # only process non-center pieces
            if (loop1 % 9) != 4:
                state = (self.match_state[loop1].value << bit_pos) & 0xFF
                cstate[ptr] |= state

                # handle overflow cases
                if bit_pos == 6:
                    cstate[ptr + 1] |= self.match_state[loop1].value >> 2
                elif bit_pos == 7:
                    cstate[ptr + 1] |= self.match_state[loop1].value >> 1

                # update bit position
                bit_pos += 3
                if bit_pos >= 8:
                    bit_pos -= 8
                    ptr += 1

        return cstate

    def __assign__(self, other: Match) -> Match:
        """Assign the current object's state to another Match object.

        Create a new Match object and copy the match_state of the given Match
        object into the new one. Ensure that all 54 positions of the cube are
        transferred correctly from the other object to the new one.

        :param other: The Match object to copy the state from.
        :type other: Match
        :returns: A new Match object with the same match_state as other.
        :rtype: Match
        """
        y = Match()
        for loop1 in range(54):
            y.match_state[loop1] = other.match_state[loop1]
        return y

    def __invert__(self) -> Match:
        """Invert the current Match object.

        Create a new Match object where each color in the current
        match_state is inverted. Specifically, any face piece with the color
        DontCare is replaced by the color corresponding to its face, while
        any other piece is set to DontCare. The center pieces of each face
        are restored to their original color, as they are fixed.

        :returns: A new Match object with the inverted match_state.
        :rtype: Match
        """
        y = Match()
        for loop1 in range(54):
            if self.match_state[loop1] == Cube_Color.DontCare:
                y.match_state[loop1] = Cube_Color(loop1 // 9)
            else:
                y.match_state[loop1] = Cube_Color.DontCare

        # restore center pieces to their original color
        for loop1 in range(6):
            y.match_state[loop1 * 9 + 4] = Cube_Color(loop1)

        return y

    def __add__(self, other: Match) -> Match:
        """Add another Match object to the current object.

        Combine the match states of the current Match object and
        the given other Match object. For each position in the cube, if the
        other object's match_state has a valid color, overwrite the
        corresponding position in the current object's match_state.
        Otherwise, the current object's color is retained.

        :param other: The Match object to add to the current object.
        :type other: Match
        :returns: A new Match object with the combined match_state.
        :rtype: Match
        """
        y = Match()
        # copy the current match_state
        for loop1 in range(54):
            y.match_state[loop1] = self.match_state[loop1]

        # override with other match_state where applicable
        for loop1 in range(54):
            if other.match_state[loop1].value < 6:
                y.match_state[loop1] = other.match_state[loop1]

        return y

    def __sub__(self, other: Match) -> Match:
        """Subtract another Match object from the current object.

        Create a new Match object by copying the current object's
        match_state. For each position where the other Match object has a
        valid color (value less than 6), the corresponding position in the
        current object's state is set to DontCare. The center pieces of each
        face are restored to their original colors, as they remain fixed.

        :param other: The Match object to subtract from the current object.
        :type other: Match
        :returns: A new Match object with the modified match_state.
        :rtype: Match
        """
        y = Match()

        # copy the current match_state
        for loop1 in range(54):
            y.match_state[loop1] = self.match_state[loop1]

        # set positions to DontCare based on the other object's match_state
        for loop1 in range(54):
            if other.match_state[loop1].value < 6:
                y.match_state[loop1] = Cube_Color.DontCare

        # restore the center pieces to their original colors
        for loop1 in range(6):
            y.match_state[loop1 * 9 + 4] = Cube_Color(loop1)

        return y

    def __iter__(self) -> Match:
        """Return an iterator for the Match object.

        Initialize the iter_index to 0, allowing iteration over the
        match_state of the current Match object. Return the Match object
        itself as the iterator.

        :returns: The Match object itself for iteration.
        :rtype: Match
        """
        self.iter_index = 0
        return self

    def __next__(self) -> List[Facelet, Cube_Color]:
        """Return the next element in the Match object during iteration.

        Return the next element from the match_state based on the current
        iter_index. Each iteration returns a list containing a
        Facelet object and its corresponding color from the match_state.
        If all 54 positions have been iterated over, raise a StopIteration
        exception.

        :returns: A list containing a Facelet object and the corresponding
                color from the match_state.
        :rtype: List[Facelet, Cube_Color]
        :raises StopIteration: If the iteration exceeds 54 elements.
        """
        if self.iter_index < 54:
            y = [Facelet(self.iter_index), self.match_state[self.iter_index]]
            self.iter_index += 1
            return y
        else:
            raise StopIteration

    def to_list(self) -> List[int]:
        """Convert the Match object to a list of integers.

        Convert the match_state of the current Match object into a list of
        integers, representing the color value of each non-center piece.
        Skip the center pieces (positions 4, 13, 22, etc.) as they
        are fixed and not included in the output list.

        :returns: A list of integers representing the color values of the
                non-center pieces.
        :rtype: List[int]
        """
        y = list()
        index = 0
        while index < 54:
            y.append(self.match_state[index].value)
            index += 1
            # skip center pieces
            if index % 9 == 4:
                index += 1

        return y

    # -------------------------------------------------------
    # Setup match operations
    # -------------------------------------------------------

    # clear up after substract/inversion
    def restore_center(self) -> None:
        """Restore the center pieces of the Match object.

        Restore the center pieces of each face in the match_state to their
        original colors. Each face has a fixed center color corresponding
        to its face index (0 to 5), which this method reassigns.

        :returns: None
        :rtype: NoneType
        """
        for loop1 in range(6):
            self.match_state[loop1 * 9 + 4] = Cube_Color(loop1)

    def clear(self) -> None:
        """Clear the Match object, setting all Facelets to 'DontCare'.

        Reset all 54 facelets in the match_state to DontCare, effectively
        clearing the match state. Afterward, restore the center pieces of
        each face to their original colors using restore_center().

        :returns: None
        :rtype: NoneType
        """
        for loop1 in range(54):
            self.match_state[loop1] = Cube_Color.DontCare
        self.restore_center()

    def add_cubie(self, facelet_name: int | str) -> None:
        """
        Add a cubie to the current match state.

        Add a cubie (a set of connected facelets) to the current match_state.
        Based on the provided facelet_name, determine the cubie to which the
        facelet belongs and update the match state for all the facelets of
        that cubie with their corresponding colors.

        :param facelet_name: The Facelets name in the cubie to add.
        :type facelet_name: int or str
        :returns: None
        :rtype: NoneType
        """
        facelets = Facelet(facelet_name).cubie()
        for facelet in facelets:
            self.match_state[int(facelet)] = facelet.color()

    def add_facelet(self, facelet_name: int | str) -> None:
        """
        Add a Facelet to the current match state.

        Add a single Facelet to the match_state. Based on the provided
        facelet_name, determine the corresponding Facelet and update its
        position in the match_state with its color.

        :param facelet_name: The name of the Facelet to add.
        :type facelet_name: int or str
        :returns: None
        :rtype: NoneType
        """
        facelet = Facelet(facelet_name)
        self.match_state[int(facelet)] = facelet.color()

    def add_layer(self, face: str = "U") -> None:
        """
        Set the match for the colors on the specified face.

        Set the match state for a particular face of the cube, applying the
        colors to the corresponding facelets based on the face name provided.
        Call the add_face method to handle the color assignment.
        The default face is the upper face ("U").

        :param face: The name of the face to set (default is "U").
        :type face: str
        :returns: None
        :rtype: NoneType
        """
        self.add_face(face)

    def add_two_layer(self, face: str = "U") -> None:
        """
        Set the match for both the face and its adjacent second layer.

        Set the match state for a given face and the adjacent second layer of
        the cube. Call first add_layer to set the colors for the specified
        face, and then apply the colors to the adjacent layer based on
        predefined face color sets. If an invalid face name is provided, an
        error is logged.

        :param face: The name of the face to set (default is "U").
        :type face: str
        :returns: None
        :rtype: NoneType
        """
        self.add_layer(face)
        try:
            color_sets = {
                "U": [10, 16, 19, 25, 28, 34, 37, 43],
                "L": [3, 5, 21, 23, 48, 50, 39, 41],
                "F": [1, 7, 30, 32, 52, 46, 14, 12],
                "R": [3, 5, 21, 23, 48, 50, 39, 41],
                "B": [30, 32, 1, 7, 46, 52, 12, 14],
                "D": [19, 25, 28, 34, 37, 43, 10, 16],
            }
            for index in color_sets[face]:
                self.match_state[index] = Cube_Color(index // 9)
        except ValueError:
            logger.error(
                f"Match.add_two_layer({face}) is an illegal face specification"
            )

    def solved(self) -> None:
        """Set the match to a fully solved cube.

        Set the match_state to represent fully solved cube configuration.
        Assign the color corresponding to each face to all 9 facelets of that
        face, ensuring that each of the six faces has its color correctly
        represented.

        :returns: None
        :rtype: NoneType
        """
        for loop1 in range(6):
            for loop2 in range(9):
                self.match_state[9 * loop1 + loop2] = Cube_Color(loop1)

    def add_cross(self, face_name: int | str) -> None:
        """Set the match for the cross on the specified face.

        Set the match state to reflect a cross on the face indicated by
        face_name.Apply first the cross color using add_cross_color,
        then update the match_state for the specified face's edge pieces to
        correspond with the correct color.
        If invalid face name is provided, log an error message.

        :param face_name: The face name to set the cross on.
        :type face_name: str or int
        :returns: None
        :rtype: NoneType
        """
        try:
            self.add_cross_color(face_name)
            color_sets = {
                "U": [12, 21, 30, 39],
                "L": [1, 19, 46, 43],
                "F": [5, 28, 48, 16],
                "R": [25, 52, 37, 7],
                "B": [3, 34, 50, 10],
                "D": [23, 32, 41, 14],
            }
            for index in color_sets[face_name]:
                self.match_state[index] = Cube_Color(index // 9)
        except ValueError:
            logger.error(
                f"""Match.add_cross({face_name})"""
                """ is an illegal face specification"""
            )

    def add_cross_color(self, face_name: int | str) -> None:
        """Set the match for a cross - but just colors on that face.

        Update the match_state to reflect the colors of the cross on the
        specified face. Identify the color corresponding to the face and apply
        it to the edge pieces that form the cross.
        If an invalid face name is provided, log an error message.

        :param face_name: The face name to set the cross color on.
        :type face_name: str or int
        :returns: None
        :rtype: NoneType
        """
        try:
            facelet = Facelet(face_name)
            face_index = facelet.color().value
            for loop1 in range(4):
                self.match_state[face_index * 9 + 2 * loop1 + 1] = Cube_Color(
                    face_index
                )
        except ValueError:
            logger.error(
                f"""Match.add_cross_color({face_name})"""
                """ is an illegal face specification"""
            )

    def add_face(self, face_name: int | str) -> None:
        """Set the match for the colors on the specified face.

        Set the match state for a particular face of the cube based on the
        face name provided. Assign colors to the corresponding facelets for
        the given face (U, L, F, R, B, or D).
        If an invalid face name is provided, log an error message.

        :param face_name: The name of the face to set (U, L, F, R, B, or D).
        :type face_name: str
        :returns: None
        :rtype: NoneType
        """
        self.add_face_color(face_name)
        try:
            color_sets = {
                "U": [9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42],
                "L": [0, 1, 2, 18, 19, 20, 45, 46, 47, 42, 43, 44],
                "F": [2, 5, 8, 27, 28, 29, 51, 48, 45, 17, 16, 15],
                "R": [6, 7, 8, 24, 25, 26, 51, 52, 53, 36, 37, 38],
                "B": [33, 34, 35, 47, 50, 53, 0, 3, 6, 9, 10, 11],
                "D": [20, 23, 26, 29, 32, 35, 38, 41, 44, 11, 14, 17],
            }
            for index in color_sets[face_name]:
                self.match_state[index] = Cube_Color(index // 9)
        except ValueError:
            logger.error(
                f"""Match.add_face({face_name})"""
                """ is an illegal face specification"""
            )

    def add_face_color(self, face_name: int | str) -> None:
        """Set the colors on the specified Facelet.

        Set all 9 facelets of a given face to the same color corresponding to
        the face_name provided. Calculate the index of the face based on
        the facelet's color and updates the match state for each facelet in
        that face.
        If an invalid face name is provided, log an error message.

        :param face_name: The name of the face to color (U, L, F, R, B, or D).
        :type face_name: str
        :returns: None
        :rtype: NoneType
        """
        try:
            facelet = Facelet(face_name)
            face_index = facelet.color().value
            for loop1 in range(9):
                current_index = face_index * 9 + loop1
                self.match_state[current_index] = Cube_Color(face_index)
        except ValueError:
            logger.error(
                f"Match.add_face_color({face_name}) is "
                ""
                """an illegal face specification"""
            )

    # -----------------------------------------------------------
    # Print output
    # -----------------------------------------------------------
    def print_piece_square(self, color_index: Cube_Color) -> str:
        """Print the color name with the color as background.

        Return a string formatted with ANSI escape codes that represents
        a colored square corresponding to the specified color.
        Each color has a specific background and text color, making it
        visually identifiable when printed in a terminal that supports
        ANSI color codes.
        If an unknown color index is provided, return a default gray square.

        :param color_index: The color index to be printed.
        :type color_index: Cube_Color
        :returns: A string containing the formatted color representation.
        :rtype: str
        """
        if color_index == Cube_Color.Red:
            text = "\033[48;5;124m\033[30m Re \033[0m"
        elif color_index == Cube_Color.White:
            text = "\033[107m\033[30m Wh \033[0m"
        elif color_index == Cube_Color.Orange:
            text = "\033[48;5;202m\033[30m Or \033[0m"
        elif color_index == Cube_Color.Yellow:
            text = "\033[48;5;11m\033[30m Ye \033[0m"
        elif color_index == Cube_Color.Blue:
            text = "\033[48;5;27m\033[30m Bl \033[0m"
        elif color_index == Cube_Color.Green:
            text = "\033[102m\033[30m Gr \033[0m"
        else:
            text = "\033[48;5;241m\033[30m    \033[0m"
        return text

    def __str__(self) -> str:
        """Convert the Match object to a string representation.

        Generate a string that visually represents the current state of the
        cube by iterating through the match_state array.
        Print the upper face, the middle layers, and the bottom face
        of the cube, formatting each piece with background colors.
        The string can be printed to provide a graphical representation
        of the cube in the console.

        :returns: A string representing the cube's current state.
        :rtype: str
        """
        cube_str = ""
        ptr = 0

        # print upper state
        cube_str += "\n"
        for loop1 in range(3):
            cube_str += "            "
            for loop2 in range(3):
                color_index = self.match_state[ptr + 3 * loop2]
                cube_str += self.print_piece_square(color_index)
            cube_str += "\n"
            ptr += 1

        # print core middle
        ptr = 9
        for loop1 in range(3):
            for loop2 in range(12):
                color_index = self.match_state[ptr + 3 * loop2]
                cube_str += self.print_piece_square(color_index)
            cube_str += "\n"
            ptr += 1

        # print down
        ptr = 45
        for loop1 in range(3):
            cube_str += "            "
            for loop2 in range(3):
                color_index = self.match_state[ptr + 3 * loop2]
                cube_str += self.print_piece_square(color_index)
            cube_str += "\n"
            ptr += 1
        cube_str += "\n"

        return cube_str


# -----------------------------------------------
# Defines Cube moves - builds up the translation
# to HEYKUBE index, and from the string notation
# ----------------------------------------------
class Moves:
    """
    Define the moves for HEYKUBE.

    Translation between cubing notication U|L|F|R|B|D and the HEYKUBE index.
    """

    def __init__(self, move_str: str = "") -> None:
        """
        Moves class constructor.

        :param move_str: A string representing the sequence of moves,
                         defaults to an empty string.
        :type move_str: str
        :returns: None
        :rtype: NoneType
        """
        self.move_list = list()
        self.move_index = 0

        # Define the direct face rotations and indices
        self.FaceRotations = {
            "U": 0,
            "L": 1,
            "F": 2,
            "R": 3,
            "B": 4,
            "D": 5,
            "U'": 8,
            "L'": 9,
            "F'": 10,
            "R'": 11,
            "B'": 12,
            "D'": 13,
            # change orientation
            "x": 16,
            "y": 17,
            "z": 18,
            "x'": 24,
            "y'": 25,
            "z'": 26,
        }
        self.InvFaceRotations = dict(
            (self.FaceRotations[k], k) for k in self.FaceRotations
        )

        # setup dual face rotaions
        self.DoubleFaceRotations = {
            "u": ["D", "y"],
            "l": ["R", "x'"],
            "f": ["B", "z"],
            "r": ["L", "x"],
            "b": ["F", "z'"],
            "d": ["U", "y'"],
            "u'": ["D'", "y'"],
            "l'": ["R'", "x"],
            "f'": ["B'", "z'"],
            "r'": ["L'", "x'"],
            "b'": ["F'", "z"],
            "d'": ["U'", "y"],
        }

        # setup dual face rotaions
        self.CenterRotations = {
            "M": ["x'", "L'", "R"],
            "E": ["y'", "U", "D'"],
            "S": ["z", "F'", "B"],
            "M'": ["x", "L", "R'"],
            "E'": ["y", "U'", "D"],
            "S'": ["z'", "F", "B'"],
        }

        # Define absolution rotations
        self.AbsFaceRotations = {
            "Wh": 0,
            "Or": 1,
            "Gr": 2,
            "Re": 3,
            "Bl": 4,
            "Ye": 5,
            "Wh'": 8,
            "Or'": 9,
            "Gr'": 10,
            "Re'": 11,
            "Bl'": 12,
            "Ye'": 13,
        }

        # add moves
        self.add_moves(move_str)

    def __repr__(self) -> str:
        """
        Compute the official string representation of a Moves object.

        :returns: The official string representation of a Moves object.
        :rtype: str
        """
        return self.__str__()

    def __iter__(self) -> Moves:
        """
        Iterate over the Moves object.

        Initialize the move_index to 0, allowing iteration over the
        move_list of the current Match object. Return the Moves object
        itself as the iterator.

        :returns: The Moves object itself for iteration.
        :rtype: Moves
        """
        self.move_index = 0
        return self

    def __len__(self) -> int:
        """
        Return the length of the Moves object.

        Return the number of moves currently stored
        in the move_list.

        :returns: The number of moves in the move_list.
        :rtype: int
        """
        return len(self.move_list)

    def __add__(self, other) -> Moves:
        """
        Combine two Moves objects.

        Combine the move list of the current Moves object with another Moves
        object and return a new Moves object.

        :param other: Another Moves object.
        :type other: Moves
        :returns: A new Moves object with the combined move lists.
        :rtype: Moves
        """
        y = Moves()
        for val in self.move_list:
            y.move_list.append(val)
        for val in other.move_list:
            y.move_list.append(val)
        return y

    def clear(self) -> None:
        """
        Clear the list of moves.

        Reset the move list to an empty list, effectively clearing
        any previously stored moves.

        :returns: None
        :rtype: NoneType
        """
        self.move_list = list()

    def absolute(self) -> Moves:
        """
        Return the reverse moves sequence to reset cube's orientation.

        Generate the reverse of the current move sequence, which would return
        the cube back to its original orientation. Additionally, set the
        orientation of the cube such that the "U" (upper) face is white and
        the "F" (front) face is green.

        :returns: A Moves object with the reverse moves.
        :rtype: Moves
        """
        # set the orientation
        self.orientation = {"U": Cube_Color.White, "F": Cube_Color.Green}

        self.order = {val: val for val in ["U", "L", "F", "R", "B", "D"]}

        reverse_moves = Moves()
        for loop1 in range(len(self.move_list)):
            move = self.move_list[len(self.move_list) - 1 - loop1]
            move_index = self.FaceRotations[move]

            # Flip the list
            if move_index & 0x8:
                move_index &= 0x7
            else:
                move_index |= 0x8
            reverse_moves.add(self.InvFaceRotations[move_index])
        return reverse_moves

    def reverse(self) -> Moves:
        """
        Reverse the moves.

        Convert clockwise to counter-clockwise moves (and vice versa).

        :returns: A Moves object with reversed move sequence.
        :rtype: Moves
        """
        reverse_moves = Moves()
        for loop1 in range(len(self.move_list)):
            move = self.move_list[len(self.move_list) - 1 - loop1]
            move_index = self.FaceRotations[move]

            # Flip the list
            if move_index & 0x8:
                move_index &= 0x7
            else:
                move_index |= 0x8
            reverse_moves.add(self.InvFaceRotations[move_index])
        return reverse_moves

    def add_moves(self, move_str: Union[str, List[Union[int, str]]]) -> None:
        """
        Add moves to the list.

        Processe a string or a list of moves and add them to the move_list.
        Handle both individual moves and groups of moves, allowing for
        repeated notations (e.g., "2x" or "3x"). The moves are identified
        either as face rotations or specific indexed moves.

        :param move_str: The move string or list of moves to process. The input
            can either be a string of moves (e.g., "U R U'") or a list of moves
            represented as integers or strings.
        :type move_str: Union[str, List[Union[int, str]]]
        :returns: None
        """
        # Deal with lists
        if isinstance(move_str, list):
            for val in move_str:
                if isinstance(val, int):
                    self.move_list.append(self.InvFaceRotations[val])
                else:
                    self.move_list.append(self.FaceRotations[val])

        # Deal with strings
        else:
            # pad to check for 2x notation
            move_str += "  "

            # Deal with groupings
            while True:
                group_start = move_str.find("(")
                if group_start == -1:
                    break

                group_end = move_str.find(")")

                rot_group = move_str[group_start + 1 : group_end]

                # Double the group
                if move_str[group_end + 1] == "2":
                    rot_group += " "
                    rot_group += rot_group
                    group_end += 1
                elif move_str[group_end + 1] == "3":
                    rot_group += " "
                    rot_group += rot_group + rot_group
                    group_end += 1

                # Rebuild string
                move_str += move_str[0:group_start]
                move_str += rot_group
                move_str += move_str[group_end + 1 :]

            # pad so we can check for extra parameters
            str_index = 0
            while str_index < len(move_str):
                if move_str[str_index] == " ":
                    str_index += 1

                # Handle regular moves
                elif move_str[str_index] in self.FaceRotations:
                    # Get move
                    next_val = move_str[str_index]
                    str_index += 1

                    num_moves = 1
                    if move_str[str_index] == "2":
                        num_moves = 2
                        str_index += 1
                    elif move_str[str_index] == "3":
                        num_moves = 3
                        str_index += 1

                    if move_str[str_index] == "'":
                        next_val += "'"
                        str_index += 1

                    for loop1 in range(num_moves):
                        self.move_list.append(next_val)

                # Handle double moves
                elif move_str[str_index] in self.DoubleFaceRotations:
                    # Get move
                    next_val = move_str[str_index]
                    str_index += 1

                    num_moves = 1
                    if move_str[str_index] == "2":
                        num_moves = 2
                        str_index += 1
                    elif move_str[str_index] == "3":
                        num_moves = 3
                        str_index += 1
                    if move_str[str_index] == "'":
                        next_val += "'"
                        str_index += 1

                    next_set = self.DoubleFaceRotations[next_val]
                    for loop1 in range(num_moves):
                        self.move_list.extend(next_set)

                # Handle double moves
                elif move_str[str_index] in self.CenterRotations:
                    # Get move
                    next_val = move_str[str_index]
                    str_index += 1

                    num_moves = 1
                    if move_str[str_index] == "2":
                        num_moves = 2
                        str_index += 1
                    elif move_str[str_index] == "3":
                        num_moves = 3
                        str_index += 1
                    if move_str[str_index] == "'":
                        next_val += "'"
                        str_index += 1

                    next_set = self.CenterRotations[next_val]
                    for loop1 in range(num_moves):
                        self.move_list.extend(next_set)

                else:
                    print("Cannot processing {}".format(move_str[str_index]))
                    str_index += 1

    def __next__(self) -> Moves:
        """
        Return the next move from the Moves object.

        Retrieve the next move from the move_list attribute of the Moves
        object, incrementing the move_index to keep track of the current
        position in the list.
        If the end of the list is reached, raise a StopIteration exception
        to signal the end of the iteration.

        :returns: The next move in the move_list.
        :rtype: Moves
        :raises StopIteration: When there are no more moves to iterate over.
        """
        if self.move_index < len(self.move_list):
            y = Moves()
            y.add(self.move_list[self.move_index])
            self.move_index += 1
            return y
        else:
            raise StopIteration

    def add(self, x: Union[int, str]) -> None:
        """
        Add the specified move to the current move list.

        Append the given move x to the move_list. The move can be
        represented either as an integer or a string, which corresponds to
        a move notation or index.

        :param x: The move to add, either as an integer or a string.
        :type x: Union[int, str]
        :returns: None
        :rtype: NoneType
        """
        self.move_list.append(x)

    def __int__(self) -> Union[int, List[int]]:
        """
        Return the direct face rotation indices of the move list.

        If the move_list contains only one move, the corresponding face
        rotation index is returned as an integer.
        If the move_list contains more than one move, a list of indices
        corresponding to each move is returned.

        :returns: An integer if there is one move, or a list of integers if
                there are multiple moves.
        :rtype: Union[int, List[int]]
        """
        if len(self.move_list) == 1:
            y = int(self.FaceRotations[self.move_list[0]])
        else:
            y = list()
            for val in self.move_list:
                y.append(int(self.FaceRotations[val]))
        return y

    def __str__(self) -> str:
        """
        Convert all the moves from the Moves object to a string.

        Concatenate all moves in the move_list into a single string,
        separating each move by a space.
        If there are multiple moves, spaces are added between them.

        :returns: A string representation of the move sequence.
        :rtype: str
        """
        move_str = ""
        for loop1, val in enumerate(self.move_list):
            move_str += self.move_list[loop1]
            if loop1 < (len(self.move_list) - 1):
                move_str += " "
        return move_str

    def __getitem__(self, index: int) -> Moves:
        """
        Return a Moves object with the move located at a specific index.

        Retrieve the move at the specified index from the move_list and
        return it as a new Moves object.
        If the index is valid, the move is added to the new Moves object.
        Otherwise, an empty Moves object is returned.

        :param index: The index of the move to retrieve.
        :type index: int
        :returns: A Moves object containing the move at the specified index.
        :rtype: Moves
        """
        y = Moves()
        if index < len(self.move_list):
            y.add(self.move_list[index])
        return y

    def __ne__(self, other: Moves) -> bool:
        """
        Check Moves inequality with another Moves object.

        Return the opposite result of the equality check between the current
        Moves object and another Moves object. Return True if the lists
        are not identical, and False if they are equal.

        :param other: The other Moves object to compare with.
        :type other: Moves
        :returns: True if the Moves objects are not equal, False otherwise.
        :rtype: bool
        """
        return not self.__eq__(other)

    def __eq__(self, other: Moves) -> bool:
        """
        Check Moves equality with another Moves object.

        Compare the move_list of the current Moves object with another
        Moves object. Return True if both lists are of the same length
        and have identical moves in the same order, and False otherwise.

        :param other: The other Moves object to compare with.
        :type other: Moves
        :returns: True if both Moves objects are equal, False otherwise.
        :rtype: bool
        """
        if len(other.move_list) != len(self.move_list):
            return False
        else:
            match = True
            for loop1 in range(len(self.move_list)):
                if self.move_list[loop1] != other.move_list[loop1]:
                    match = False
                    break
            return match

    def scramble(self, num_rot: int) -> None:
        """
        Generate a random scramble of moves.

        Generate a random sequence of moves for the cube, based on the number
        of rotations specified by num_rot. Currently use a simple
        randomization method.

        TODO: Update to generate a WCA (World Cube Association)-type scramble.

        :param num_rot: Number of random rotations for the scramble.
        :type num_rot: int
        :returns: None
        :rtype: NoneType
        """
        self.randomize(num_rot)

    def pattern_enable(self) -> None:
        """
        Set the Moves object to a specific pattern enable sequence.

        Clear the current moves and then add a predefined sequence of moves,
        "L' L' D' D' D D L L", which is used to enable a specific pattern.

        :returns: None
        :rtype: NoneType
        """
        self.clear()
        self.add_moves("L' L' D' D' D D L L")

    def hints_on_off(self) -> None:
        """
        Set the Moves object to a specific hints on/off sequence.

        Clear the current moves and then add a predefined sequence of moves,
        "R R D D D' D' R' R'", which is used to toggle hints on or off.

        :returns: None
        :rtype: NoneType
        """
        self.clear()
        self.add_moves("R R D D D' D' R' R'")

    def randomize(self, num_rot: int) -> None:
        """
        Generate a random scramble of moves for the cube.

        Create a randomized list of moves with the specified number of
        rotations (num_rot). Ensure that no two consecutive moves are the
        inverse of each other. The generated moves are stored in the
        move_list attribute.
        The current implementation is a basic randomization and needs to
        follow the WCA (World Cube Association) scrambling standards.

        :param num_rot: The number of rotations to include in the scramble.
        :type num_rot: int
        :returns: None
        :rtype: NoneType
        """
        self.move_list = list()
        inv_last_move = random.randint(0, 5) | (random.randint(0, 1) << 3)
        for loop1 in range(num_rot):
            # make sure it's not just the inverted move
            next_move = inv_last_move
            while next_move == inv_last_move:
                next_move = random.randint(0, 5) | (random.randint(0, 1) << 3)
            inv_last_move = next_move ^ 0x8

            # Add the list
            self.move_list.append(self.InvFaceRotations[next_move])
        logger.info("Randomized moves: {}".format(self.move_list))

    def from_string(self, rot_str: str) -> None:
        """
        Populate the Moves object from a string representation of moves.

        Parse the provided string (rot_str) containing rotation commands
        and convert them into the corresponding moves.
        The format of the string should adhere to the defined rotation
        notations, such as single letters for face turns and optional
        modifiers for direction (e.g., '2' for double turns, "'" for
        counter-clockwise). The moves are added to the move_list
        attribute of the Moves object.

        :param rot_str: The string representation of moves to parse.
        :type rot_str: str
        :returns: None
        :rtype: NoneType
        """
        pass


# Defines Cube Faces and Colors
class Cube_Color(Enum):
    """
    Enum representing the colors used to define cube faces and a neutral one.

    Each color is associated with a unique integer value, which can be
    used for indexing or other purposes in the cube representation.

    Attributes:
        White (int): Represents the color white on the cube.
        Orange (int): Represents the color orange on the cube.
        Green (int): Represents the color green on the cube.
        Red (int): Represents the color red on the cube.
        Blue (int): Represents the color blue on the cube.
        Yellow (int): Represents the color yellow on the cube.
        DontCare (int): Represents a neutral color for facelets.
    """

    White = 0
    Orange = 1
    Green = 2
    Red = 3
    Blue = 4
    Yellow = 5
    DontCare = 6


# -------------------------------------------
# Define Cube Facelet locations
# Helps in search for faces, and encoding
# -------------------------------------------
class Facelet:
    """
    Define Facelet class.

    A HEYKUBE facelet represents an individual colored square on a HEYKUBE
    face. It serves as a basic unit for cube representation and manipulation.
    """

    def __init__(self, facelet_name: Optional[Union[int, str]] = None) -> None:
        """
        Facelet class constructor.

        :param facelete_name: Facelet name
        :type facelet_name: int or str, optional
        :returns: None
        :rtype: NoneType
        """
        # define facelets
        self.facelets = {
            # UP FACE
            "ULB": 0,
            "UB": 3,
            "URB": 6,
            "UL": 1,
            "U": 4,
            "UR": 7,
            "ULF": 2,
            "UF": 5,
            "UFR": 8,
            # left FACE
            "LUB": 9,
            "LU": 12,
            "LUF": 15,
            "LB": 10,
            "L": 13,
            "LF": 16,
            "LBD": 11,
            "LD": 14,
            "LFD": 17,
            # Front FACE
            "FUL": 18,
            "FU": 21,
            "FUR": 24,
            "FL": 19,
            "F": 22,
            "FR": 25,
            "FLD": 20,
            "FD": 23,
            "FRD": 26,
            # Right FACE
            "RUF": 27,
            "RU": 30,
            "RUB": 33,
            "RF": 28,
            "R": 31,
            "RB": 34,
            "RFD": 29,
            "RD": 32,
            "RBD": 35,
            # Back FACE
            "BUR": 36,
            "BU": 39,
            "BUL": 42,
            "BR": 37,
            "B": 40,
            "BL": 43,
            "BRD": 38,
            "BD": 41,
            "BLD": 44,
            # Down FACE
            "DLF": 45,
            "DF": 48,
            "DFR": 51,
            "DL": 46,
            "D": 49,
            "DR": 52,
            "DLB": 47,
            "DB": 50,
            "DRB": 53,
        }
        # get reverse LUT
        self.inv_facelets = dict()
        for keys in self.facelets.keys():
            self.inv_facelets[self.facelets[keys]] = keys

        # zero the iterator
        self.iter_index = 0

        # assing the value
        if isinstance(facelet_name, int):
            self.index = facelet_name
        elif facelet_name == "":
            self.index = 4
        else:
            # reorder
            if len(facelet_name) == 3:
                second_facelet = int(Facelet(facelet_name[1]))
                third_facelet = int(Facelet(facelet_name[2]))
                if second_facelet > third_facelet:
                    facelet_name = "{}{}{}".format(
                        facelet_name[0], facelet_name[2], facelet_name[1]
                    )
            # get index
            self.index = self.facelets[facelet_name]

    def color(self) -> Cube_Color:
        """
        Return the current Facelet color.

        The color is determined by dividing the facelet index by 9, mapping it
        to the corresponding Cube_Color enumeration.

        :returns: The color of the Facelet as a Cube_Color enum value.
        :rtype: Cube_Color
        """
        return Cube_Color(self.index // 9)

    def __eq__(self, other: Facelet) -> bool:
        """
        Check Facelet equality with another Facelet.

        Compare the integer representation of the current Facelet object with
        the integer representation of another Facelet object to determine
        equality.

        :param other: The other Facelet to compare against.
        :type other: Facelet
        :returns: True if the Facelets are equal, otherwise False.
        :rtype: bool
        """
        return int(self) == int(other)

    def __le__(self, other: Facelet) -> bool:
        """
        Check if the Facelet object is less than or equal to another Facelet.

        Compare the index of the current Facelet instance with the integer
        representation of another Facelet.

        :param other: The Facelet to compare against.
        :type other: Facelet
        :returns: True if the current Facelet's index is less than or equal,
                otherwise False.
        :rtype: bool
        """
        return not self.__gt__(other)

    def __gt__(self, other: Facelet) -> bool:
        """
        Check if the Facelet object is greater than another Facelet.

        Compare the index of the current Facelet object with the integer
        representation of another Facelet.

        :param other: The Facelet to compare against.
        :type other: Facelet
        :returns: True if the current index is greater, otherwise False.
        :rtype: bool
        """
        return self.index > int(other)

    def cubie(self) -> List[Facelet]:
        """
        Construct a cubie, an individual small cube piece from the cube.

        Generate a list of Facelet objects that make up a cubie based on the
        current Facelet. A cubie can consist of one, two, or three Facelets,
        depending on its configuration in the cube.

        :returns: A list of Facelet objects representing the cubie.
        :rtype: List[Facelet]
        """
        # get name of facelet
        facelet_name = self.__str__()
        facelet = Facelet(facelet_name)
        next_facelet = Facelet(f"{facelet_name[1]}{facelet_name[0]}")

        cubie_facelets = list()

        if len(facelet_name) == 1:
            cubie_facelets.append(facelet)
        elif len(facelet_name) == 2:
            cubie_facelets.append(facelet)
            cubie_facelets.append(next_facelet)
        elif len(facelet_name) == 3:
            cubie_facelets = list()
            for loop1 in range(3):
                # get all 3 orders
                name = "{}{}{}".format(
                    facelet_name[loop1],
                    facelet_name[(loop1 + 1) % 3],
                    facelet_name[(loop1 + 2) % 3],
                )
                # sort it
                if Facelet(name[1]) > Facelet(name[2]):
                    name = f"{name[0]}{name[2]}{name[1]}"
                cubie_facelets.append(Facelet(name))

        return cubie_facelets

    def __int__(self) -> int:
        """
        Convert the current Facelet to its index.

        Return the index of the Facelet, allowing for easy conversion to an
        integer representation.

        :returns: The index of the current Facelet.
        :rtype: int
        """
        return self.index

    def __str__(self) -> str:
        """
        Return the current Facelet face.

        Provide a string representation of the Facelet, corresponding to its
        facelet name.

        :returns: The name of the facelet as a string.
        :rtype: str
        """
        return self.inv_facelets[self.index]

    def __iter__(self) -> Facelet:
        """
        Iterate over the Facelet object.

        Initialize the iterator index to zero, allowing for iteration over
        the facelets.

        :returns: The current Facelet object for iteration.
        :rtype: Facelet
        """
        self.iter_index = 0
        return self

    def __next__(self) -> Facelet:
        """
        Return the next element of the Facelet object.

        Retrieve the next facelet name during iteration.
        Raise StopIteration if the end of the iteration is reached.

        :returns: The next facelet
        :rtype: Facelet
        :raises StopIteration: If there are no more facelets to iterate.
        """
        if self.iter_index < 54:
            y = self.inv_facelets[self.iter_index]
            self.iter_index += 1
            return y
        else:
            raise StopIteration


# ---------------------------------------------------
# Main class to hold the model of a 3x3 cube
# ---------------------------------------------------
class Cube:
    """
    Define the Cube class.

    Hold the model of a 3x3 cube.
    """

    def __init__(self) -> None:
        """
        Cube class constructor.

        :returns: None
        :rtype: NoneType
        """
        # Initialize the state
        self.state = list()
        for loop1 in range(54):
            self.state.append(loop1)

        # Defines debug level
        self.debug = 2

        # set the orientation
        self.orientation = {"U": Cube_Color.White, "F": Cube_Color.Green}

        # set moves
        self.moves = Moves()
        self.seq_num = 0

        # Setup state
        self.EdgePairs = [
            # Up
            [Facelet("UF"), Facelet("FU")],
            [Facelet("UR"), Facelet("RU")],
            [Facelet("UB"), Facelet("BU")],
            [Facelet("UL"), Facelet("LU")],
            # Down
            [Facelet("DF"), Facelet("FD")],
            [Facelet("DR"), Facelet("RD")],
            [Facelet("DB"), Facelet("BD")],
            [Facelet("DL"), Facelet("LD")],
            # middle
            [Facelet("FR"), Facelet("RF")],
            [Facelet("FL"), Facelet("LF")],
            [Facelet("BR"), Facelet("RB")],
            [Facelet("BL"), Facelet("LB")],
        ]

        # Corner sets
        self.CornerSets = [
            # Up
            [Facelet("UFR"), Facelet("FUR"), Facelet("RUF")],
            [Facelet("URB"), Facelet("RUB"), Facelet("BUR")],
            [Facelet("ULB"), Facelet("BUL"), Facelet("LUB")],
            [Facelet("ULF"), Facelet("LUF"), Facelet("FUL")],
            # Down
            [Facelet("DFR"), Facelet("RFD"), Facelet("FRD")],
            [Facelet("DLF"), Facelet("FLD"), Facelet("LFD")],
            [Facelet("DLB"), Facelet("LBD"), Facelet("BLD")],
            [Facelet("DRB"), Facelet("BRD"), Facelet("RBD")],
        ]

        self.rotationTable = [
            # ULFRBD
            [
                2,
                5,
                8,
                1,
                4,
                7,
                0,
                3,
                6,
                18,
                10,
                11,
                21,
                13,
                14,
                24,
                16,
                17,
                27,
                19,
                20,
                30,
                22,
                23,
                33,
                25,
                26,
                36,
                28,
                29,
                39,
                31,
                32,
                42,
                34,
                35,
                9,
                37,
                38,
                12,
                40,
                41,
                15,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
            ],
            [
                44,
                43,
                42,
                3,
                4,
                5,
                6,
                7,
                8,
                11,
                14,
                17,
                10,
                13,
                16,
                9,
                12,
                15,
                0,
                1,
                2,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                47,
                46,
                45,
                18,
                19,
                20,
                48,
                49,
                50,
                51,
                52,
                53,
            ],
            [
                0,
                1,
                17,
                3,
                4,
                16,
                6,
                7,
                15,
                9,
                10,
                11,
                12,
                13,
                14,
                45,
                48,
                51,
                20,
                23,
                26,
                19,
                22,
                25,
                18,
                21,
                24,
                2,
                5,
                8,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                29,
                46,
                47,
                28,
                49,
                50,
                27,
                52,
                53,
            ],
            [
                0,
                1,
                2,
                3,
                4,
                5,
                24,
                25,
                26,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                51,
                52,
                53,
                29,
                32,
                35,
                28,
                31,
                34,
                27,
                30,
                33,
                8,
                7,
                6,
                39,
                40,
                41,
                42,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                38,
                37,
                36,
            ],
            [
                33,
                1,
                2,
                34,
                4,
                5,
                35,
                7,
                8,
                6,
                3,
                0,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                53,
                50,
                47,
                38,
                41,
                44,
                37,
                40,
                43,
                36,
                39,
                42,
                45,
                46,
                9,
                48,
                49,
                10,
                51,
                52,
                11,
            ],
            [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                38,
                12,
                13,
                41,
                15,
                16,
                44,
                18,
                19,
                11,
                21,
                22,
                14,
                24,
                25,
                17,
                27,
                28,
                20,
                30,
                31,
                23,
                33,
                34,
                26,
                36,
                37,
                29,
                39,
                40,
                32,
                42,
                43,
                35,
                47,
                50,
                53,
                46,
                49,
                52,
                45,
                48,
                51,
            ],
            # (ULFRBD)'
            [
                6,
                3,
                0,
                7,
                4,
                1,
                8,
                5,
                2,
                36,
                10,
                11,
                39,
                13,
                14,
                42,
                16,
                17,
                9,
                19,
                20,
                12,
                22,
                23,
                15,
                25,
                26,
                18,
                28,
                29,
                21,
                31,
                32,
                24,
                34,
                35,
                27,
                37,
                38,
                30,
                40,
                41,
                33,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
            ],
            [
                18,
                19,
                20,
                3,
                4,
                5,
                6,
                7,
                8,
                15,
                12,
                9,
                16,
                13,
                10,
                17,
                14,
                11,
                45,
                46,
                47,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                2,
                1,
                0,
                44,
                43,
                42,
                48,
                49,
                50,
                51,
                52,
                53,
            ],
            [
                0,
                1,
                27,
                3,
                4,
                28,
                6,
                7,
                29,
                9,
                10,
                11,
                12,
                13,
                14,
                8,
                5,
                2,
                24,
                21,
                18,
                25,
                22,
                19,
                26,
                23,
                20,
                51,
                48,
                45,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                15,
                46,
                47,
                16,
                49,
                50,
                17,
                52,
                53,
            ],
            [
                0,
                1,
                2,
                3,
                4,
                5,
                38,
                37,
                36,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                6,
                7,
                8,
                33,
                30,
                27,
                34,
                31,
                28,
                35,
                32,
                29,
                53,
                52,
                51,
                39,
                40,
                41,
                42,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                24,
                25,
                26,
            ],
            [
                11,
                1,
                2,
                10,
                4,
                5,
                9,
                7,
                8,
                47,
                50,
                53,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                0,
                3,
                6,
                42,
                39,
                36,
                43,
                40,
                37,
                44,
                41,
                38,
                45,
                46,
                35,
                48,
                49,
                34,
                51,
                52,
                33,
            ],
            [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                20,
                12,
                13,
                23,
                15,
                16,
                26,
                18,
                19,
                29,
                21,
                22,
                32,
                24,
                25,
                35,
                27,
                28,
                38,
                30,
                31,
                41,
                33,
                34,
                44,
                36,
                37,
                11,
                39,
                40,
                14,
                42,
                43,
                17,
                51,
                48,
                45,
                52,
                49,
                46,
                53,
                50,
                47,
            ],
            # xyz
            [
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                15,
                12,
                9,
                16,
                13,
                10,
                17,
                14,
                11,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                29,
                32,
                35,
                28,
                31,
                34,
                27,
                30,
                33,
                8,
                7,
                6,
                5,
                4,
                3,
                2,
                1,
                0,
                44,
                43,
                42,
                41,
                40,
                39,
                38,
                37,
                36,
            ],
            [
                2,
                5,
                8,
                1,
                4,
                7,
                0,
                3,
                6,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                51,
                48,
                45,
                52,
                49,
                46,
                53,
                50,
                47,
            ],
            [
                11,
                14,
                17,
                10,
                13,
                16,
                9,
                12,
                15,
                47,
                50,
                53,
                46,
                49,
                52,
                45,
                48,
                51,
                20,
                23,
                26,
                19,
                22,
                25,
                18,
                21,
                24,
                2,
                5,
                8,
                1,
                4,
                7,
                0,
                3,
                6,
                42,
                39,
                36,
                43,
                40,
                37,
                44,
                41,
                38,
                29,
                32,
                35,
                28,
                31,
                34,
                27,
                30,
                33,
            ],
            # (xyz)'
            [
                44,
                43,
                42,
                41,
                40,
                39,
                38,
                37,
                36,
                11,
                14,
                17,
                10,
                13,
                16,
                9,
                12,
                15,
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                33,
                30,
                27,
                34,
                31,
                28,
                35,
                32,
                29,
                53,
                52,
                51,
                50,
                49,
                48,
                47,
                46,
                45,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
            ],
            [
                6,
                3,
                0,
                7,
                4,
                1,
                8,
                5,
                2,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                47,
                50,
                53,
                46,
                49,
                52,
                45,
                48,
                51,
            ],
            [
                33,
                30,
                27,
                34,
                31,
                28,
                35,
                32,
                29,
                6,
                3,
                0,
                7,
                4,
                1,
                8,
                5,
                2,
                24,
                21,
                18,
                25,
                22,
                19,
                26,
                23,
                20,
                51,
                48,
                45,
                52,
                49,
                46,
                53,
                50,
                47,
                38,
                41,
                44,
                37,
                40,
                43,
                36,
                39,
                42,
                15,
                12,
                9,
                16,
                13,
                10,
                17,
                14,
                11,
            ],
        ]

    def initialize(self) -> None:
        """
        Initialize the state list with default values for a solved cube.

        Reset the cube state to the default solved position by setting each
        element of the state list to its index. Also clear the current move
        sequence.

        :returns: None
        :rtype: NoneType
        """
        self.clear_moves()
        for loop1 in range(54):
            self.state[loop1] = loop1

    def apply_moves(self, moves: Moves) -> None:
        """
        Apply a sequence of moves to the current Cube object.

        Iterate through the given moves, update the cube's state based
        on a predefined rotation table, and maintain a sequence number
        for tracking the number of moves applied.

        :param moves: A sequence of moves to apply to the cube. Each move is
                    representing a rotation or transformation.
        :type moves: Moves
        :returns: None
        :rtype: NoneType
        """
        # go through the moves
        for move in moves:
            # create new state
            new_state = [0] * 54

            # get table index
            move_index = int(move)
            if (move_index >= 0) and (move_index <= 5):
                table_index = move_index
            elif (move_index >= 8) and (move_index <= 13):
                table_index = move_index - 2
            elif (move_index >= 16) and (move_index <= 18):
                table_index = move_index - 4
            elif (move_index >= 24) and (move_index <= 26):
                table_index = move_index - 9
            else:
                table_index = None
                logger.error(f"Illegal move specification {move}")

            # with a valid entry run the move
            if table_index is not None:
                rotSet = self.rotationTable[table_index]
                for loop1 in range(54):
                    new_state[loop1] = self.state[rotSet[loop1]]
                self.state = new_state

                # keep track
                # print('Adding {} move to the cube'.format(move))
                self.moves.add_moves([move_index])
                # updating seq number
                self.seq_num += 1
                self.seq_num &= 0xFF

    def get_orientation(self) -> Dict:
        """
        Get the current Cube orientation with UP and FRONT faces.

        Retrieve the colors of the UP and FRONT faces of the cube, construct
        a dictionary to represent the current orientation, and log
        the orientation.

        :returns: A dictionary containing the colors of the UP and FRONT
                cube faces, with keys "U" and "F" respectively.
        :rtype: Dict
        """
        orientation = dict()

        orientation["U"] = self.get_location_color(Facelet("U"))
        orientation["F"] = self.get_location_color(Facelet("F"))
        logger.info("Orientation = {}".format(orientation))

        return orientation

    def reset_orientation(self) -> None:
        """
        Reset the cube orientation to default reference position.

        Reorient the cube based on the color of the facelets, specifically
        ensuring the white face is oriented correctly and then adjusting
        the position of the green face as needed.

        :returns: None
        :rtype: NoneType
        """
        logger.info("Resetting orientation")

        # moves the white face
        if self.get_location_color(Facelet("L")) == Cube_Color.White:
            self.apply_moves(Moves("z"))
        elif self.get_location_color(Facelet("F")) == Cube_Color.White:
            self.apply_moves(Moves("x"))
        elif self.get_location_color(Facelet("R")) == Cube_Color.White:
            self.apply_moves(Moves("z'"))
        elif self.get_location_color(Facelet("B")) == Cube_Color.White:
            self.apply_moves(Moves("x'"))
        elif self.get_location_color(Facelet("D")) == Cube_Color.White:
            self.apply_moves(Moves("x x"))
        # print(self.__str__())

        # moves the Green face
        if self.get_location_color(Facelet("L")) == Cube_Color.Green:
            self.apply_moves(Moves("y'"))
        elif self.get_location_color(Facelet("R")) == Cube_Color.Green:
            self.apply_moves(Moves("y"))
        elif self.get_location_color(Facelet("B")) == Cube_Color.Green:
            self.apply_moves(Moves("y y"))
        # print(self.__str__())

    def is_solved(self) -> bool:
        """
        Check if the cube is solved.

        Iterate through the cube's state to verify that each facelet is in
        its correct position, returning True if all facelets are correctly
        aligned and False otherwise.

        :returns: True if the cube is solved, False otherwise
        :rtype: bool
        """
        solved = True
        for loop1 in range(54):
            if self.state[loop1] != loop1:
                solved = False
        return solved

    def test_match(self, match: Match) -> bool:
        """
        Check if the match corresponds to the current cube's state.

        Compare the current state of the cube with a given match object,
        checking each facelet color against the expected color in the match.
        If all matched colors correspond or are set to 'DontCare',
        return True; otherwise, return False.

        :param match: The match object containing the expected cube state.
        :type match: Match
        :returns: True if the current state matches match, False otherwise.
        :rtype: bool
        """
        match_test = True
        for loop1 in range(54):
            if match.match_state[loop1] != Cube_Color.DontCare:
                facelet_color = Cube_Color(self.state[loop1] // 9)
                if facelet_color != match.match_state[loop1]:
                    match_test = False
        return match_test

    # Returns current cube state
    def get_state(self) -> List[int]:
        """
        Return the current cube state.

        Encode the cube's current configuration into a state representation
        and return it as a list of integers.

        :returns: A list of integers representing the current state.
        :rtype: List[int]
        """
        return self.encode_state()

    # decode a permuation
    def decodePerm(self, lex: int, n: int) -> List[int]:
        """
        Decode a cube permutation.

        Decode a given permutation value (lex) into a list of indices
        representing the positions of the pieces in the permutation.

        :param lex: The lexicographic index of the permutation to decode.
        :type lex: int
        :param n: The total number of elements in the permutation.
        :type n: int
        :returns: A list of integers representing the decoded permutation.
        :rtype: List[int]
        """
        a = list()
        for loop1 in range(n):
            a.append(0)

        i = n - 2
        while i >= 0:
            a[i] = lex % (n - i)
            lex //= n - i
            for j in range(i + 1, n):
                if a[j] >= a[i]:
                    a[j] += 1
            i -= 1
        return a

    def encodePerm(self, a: List[int]) -> int:
        """
        Encode a cube permutation.

        Take a list of indices representing a permutation and encode it into a
        single integer value. The encoding is based on the lexicographic order
        of the permutations.

        :param a: A list of integers representing the permutation indices.
        :type a: List[int]
        :returns: An integer representing the encoded permutation, or -1 if the
                permutation is invalid.
        :rtype: int
        """
        # Permtation enocder
        perm_popcount64 = [
            0,
            1,
            1,
            2,
            1,
            2,
            2,
            3,
            1,
            2,
            2,
            3,
            2,
            3,
            3,
            4,
            1,
            2,
            2,
            3,
            2,
            3,
            3,
            4,
            2,
            3,
            3,
            4,
            3,
            4,
            4,
            5,
            1,
            2,
            2,
            3,
            2,
            3,
            3,
            4,
            2,
            3,
            3,
            4,
            3,
            4,
            4,
            5,
            2,
            3,
            3,
            4,
            3,
            4,
            4,
            5,
            3,
            4,
            4,
            5,
            4,
            5,
            5,
            6,
        ]

        n = len(a)
        bits = 0
        r = 0
        for i in range(n):
            bits |= 1 << a[i]
            low = ((1 << a[i]) - 1) & bits
            r = (
                r * (n - i)
                + a[i]
                - perm_popcount64[low >> 6]
                - perm_popcount64[low & 63]
            )
        if (bits + 1) != (1 << n):
            return -1
        return r

    # --------------------------------------------------------
    # Encoding format is derived from the spec
    # https://experiments.cubing.net/cubing.js/spec/binary/index.html
    #
    # it appears to bit-reverse over original format
    # --------------------------------------------------------
    def encode_state(self) -> List[int]:
        """
        Encode the Cube state to a list of byte.

        Encode the current state of the cube into an 11-byte list
        representation. Calculate the orientation of edges and corners,
        as well as the permutation of the cube, allowing for a compact
        representation of the cube's state.

        :returns: A list of integers representing the encoded cube state.
        :rtype: List[int]
        """
        # setup 11 byte encoding
        cstate = [0] * 11

        # -------------------------------------------------------
        # get the 12 edges pieces
        # -------------------------------------------------------
        edge_orient = 0
        cubies = [-1] * 12

        for loop1 in range(12):
            # get piece
            edgePiece = self.state[int(self.EdgePairs[loop1][0])]

            # find the piece number
            edge_orient <<= 1
            for loop2 in range(12):
                for loop3 in range(2):
                    if edgePiece == int(self.EdgePairs[loop2][loop3]):
                        cubies[loop1] = loop2
                        edge_orient += loop3
                if cubies[loop1] >= 0:
                    break

        # get the permutation
        encode = self.encodePerm(cubies) & 0x1FFFFFFF
        for loop1 in range(4):
            cstate[loop1] = encode & 0xFF
            encode >>= 8

        # encode the state variable
        cstate[3] |= (edge_orient & 0x7) << 5
        edge_orient >>= 3
        cstate[4] = edge_orient & 0xFF
        edge_orient >>= 8
        cstate[5] = edge_orient & 0x1

        # ------------------------------------------------------
        # Get the corner Pieces
        # ------------------------------------------------------
        corner_orient = 0
        cubies = [-1] * 8
        for loop1 in range(8):
            cornerPiece = self.state[int(self.CornerSets[loop1][0])]

            corner_orient *= 3
            for loop2 in range(8):
                for loop3 in range(3):
                    if cornerPiece == int(self.CornerSets[loop2][loop3]):
                        cubies[loop1] = loop2
                        corner_orient += loop3
                if cubies[loop1] >= 0:
                    break

        # get the permutation
        encode = self.encodePerm(cubies) & 0xFFFF
        cstate[5] |= (encode & 0x7F) << 1
        encode >>= 7
        cstate[6] = encode & 0xFF
        encode >>= 8
        cstate[7] = encode & 0x1

        # encoder corner orientation
        cstate[7] |= (corner_orient & 0x7F) << 1
        corner_orient >>= 7
        cstate[8] = corner_orient & 0x3F

        # puzzle orientation
        # always U, L = 0,0
        # Center locations are encoded
        center_orient = 0
        cstate[9] = 0x8 | ((center_orient & 0xF) << 4)
        cstate[10] = center_orient >> 4

        return cstate

    # gets list of perm/orientation from cstate
    def recover_cstate_data(
        self, cstate: List[int]
    ) -> Tuple[bool, List[int], int, List[int], int, int]:
        """
        Recover the permutation and orientation from the given cstate.

        Decode the cube's state information, including edge and corner
        permutations and orientations, from the provided cstate list.
        Check the validity of the state and returns the relevant data
        for further processing.

        :param cstate: A list of integers representing the encoded cube state.
        :type cstate: List[int]
        :returns: A tuple containing a validity flag, edge permutation,
                edge orientation, corner permutation, corner orientation,
                and center orientation.
        :rtype: Tuple[bool, List[int], int, List[int], int, int]
        """
        valid_state = True

        # get edge perm
        r = cstate[0]
        r |= cstate[1] << 8
        r |= cstate[2] << 16
        r |= (cstate[3] & 0x1F) << 24

        edge_orient = cstate[3] >> 5
        edge_orient |= cstate[4] << 3
        edge_orient |= (cstate[5] & 0x1) << 11

        # decode permutation
        edge_perm = self.decodePerm(r, 12)

        # get corner perm
        r = cstate[5] >> 1
        r |= cstate[6] << 7
        r |= (cstate[7] & 0x1) << 15

        # decode permutation
        corner_perm = self.decodePerm(r, 8)

        # get corner orientation
        corner_orient = cstate[7] >> 1
        corner_orient |= (cstate[8] & 0x3F) << 7

        # get position of Faces - must be 0x0, 0x0
        pos = cstate[8] >> 6
        pos |= (cstate[9] & 0x7) << 2
        if pos != 0:
            valid_state = False

        # get order
        if cstate[9] & 0x8:
            center_orient = cstate[9] >> 4
            center_orient |= cstate[10] << 4
        else:
            center_orient = 0

        return (
            valid_state,
            edge_perm,
            edge_orient,
            corner_perm,
            corner_orient,
            center_orient,
        )

    # --------------------------------------------------------------
    # recover decoded state
    # --------------------------------------------------------------
    def decode_state(self, cstate: List[int]) -> Tuple[bool, List[int], int]:
        """
        Decode the cube state to reconstruct its configurations.

        Take an encoded cube state and reconstruct the cube's configurations
        by determining the placement and orientation of edge and corner.
        Check the validity of the reconstructed state.

        :param cstate: A list of integers representing the encoded cube state.
        :type cstate: List[int]
        :returns: A tuple containing a validity flag, the reconstructed state,
                and the center orientation.
        :rtype: Tuple[bool, List[int], int]
        """
        # set new list
        new_state = list()
        for loop1 in range(54):
            new_state.append(loop1)

        # Set the center stage
        for loop1 in range(6):
            centerPiece = loop1 * 9 + 4
            new_state[centerPiece] = centerPiece

        # get the permuatioitatio
        (
            valid_state,
            edge_perm,
            edge_orient,
            corner_perm,
            corner_orient,
            center_orient,
        ) = self.recover_cstate_data(cstate)
        # put edge pieces into location
        loop1 = 11
        while loop1 >= 0:
            orient_index = edge_orient & 0x1
            for loop2 in range(2):
                edgeLoc = int(self.EdgePairs[loop1][loop2])
                edgePiece = int(self.EdgePairs[edge_perm[loop1]][orient_index])
                new_state[edgeLoc] = edgePiece
                orient_index ^= 0x1
            # shift out orientation
            edge_orient >>= 1
            loop1 -= 1

        # Get corner permutation
        loop1 = 7
        while loop1 >= 0:
            orient_index = corner_orient % 3
            for loop2 in range(3):
                cornerLoc = int(self.CornerSets[loop1][loop2])
                piece = self.CornerSets[corner_perm[loop1]][orient_index]
                cornerPiece = int(piece)
                orient_index = (orient_index + 1) % 3

                new_state[cornerLoc] = cornerPiece

            # shift out
            corner_orient //= 3
            loop1 -= 1

        # Check the final sum
        piece_sum = 0
        for loop1 in range(54):
            piece_sum += new_state[loop1]
        if piece_sum != 1431:
            valid_state = False

        return (valid_state, new_state, center_orient)

    def clear_moves(self) -> None:
        """
        Clear all moves from the device.

        Reset the move history of the cube, ensuring that no previous moves
        are retained in the internal state.

        :returns: None
        :rtype: NoneType
        """
        self.moves.clear()

    # Sets state from cstate
    def set_state(self, cstate: List[int]) -> None:
        """
        Update the internal Cube state.

        Set the cube's state based on the provided state list, which must
        contain at least 20 integers. Updates the cube's internal state,
        moves, and sequence number if the provided state is valid.

        :param cstate: A list of integers representing the cube's state.
        :type cstate: List[int]
        :returns: None
        :rtype: NoneType
        """
        if len(cstate) < 20:
            print("Need a list of 20 integers")
            return False

        # Update cube states
        valid_cube, new_state, center_orient = self.decode_state(cstate)
        if valid_cube:
            self.state = new_state

        # Update moves
        new_seq_num = cstate[11]
        new_moves = (new_seq_num - self.seq_num) % 256

        move_list = list()
        for loop1 in range(9):
            next_move = cstate[loop1 + 12] & 0xF
            if next_move != 0xF:
                move_list.append(next_move)
            next_move = (cstate[loop1 + 12] >> 4) & 0xF
            if next_move != 0xF:
                move_list.append(next_move)
        # shorten to new moves
        # print(f'new_seq_num = {new_seq_num}, prev = {self.seq_num}')
        # print('Shorting: ', move_list)
        if new_moves < len(move_list):
            move_list = move_list[len(move_list) - new_moves :]
        # print('By {} moves: '.format(new_moves),  move_list)
        # Update tracking
        self.moves.add_moves(move_list)
        self.seq_num = new_seq_num
        self.timestamp = (cstate[21] + cstate[22] << 8) / 512.0

        return valid_cube

    # --------------------------------------------------------
    # Helper functions
    # --------------------------------------------------------
    def get_location_color(self, cube_index: Facelet | int) -> Cube_Color:
        """
        Return the color of the selected cube at the current state.

        Retrieve the color corresponding to the specified cube index based on
        the current state of the cube. The cube index should be an integer
        representing the position of the facelet or a Facelet object.

        :param cube_index: The cube index for which to retrieve the color.
        :param cube_index: Facelet or int
        :returns: The color of the specified cube.
        :rtype: Cube_Color
        """
        color = Cube_Color(self.state[int(cube_index)] // 9)
        return color

    def get_piece_color(self, cube_index: Facelet | int) -> Cube_Color:
        """
        Return the color of the selected cube when solved.

        Retrieve the color corresponding to the specified cube index based on
        the solved state of the cube. The cube index should be an integer
        representing the position of the facelet or a Facelet object.

        :param cube_index: The cube index for which to retrieve the color.
        :type cube_inde: Facelet or int
        :returns: The color of the specified cube in the solved position.
        :rtype: Cube_Color
        """
        color = Cube_Color(int(cube_index) // 9)
        return color

    def print_piece_square(
        self, val: Facelet | int, label: bool = True
    ) -> str:
        """
        Print on console the piece of cube with the color as background.

        Generate a string that represents a piece of the cube, with its
        background color corresponding to the piece's color in the cube.
        The piece can also be optionally labeled with its index value.

        :param val: The index of the cube piece to print.
        :type val: Facelet of int
        :param label: A boolean flag indicating whether to include the
                    piece's index in the output. Defaults to True.
        :type label: bool
        :returns: A formatted string with ANSI color codes for console output.
        :rtype: str
        """
        color_index = self.get_piece_color(val)
        text = ""
        if color_index == Cube_Color.Red:
            text = "\033[101m"
            text = "\033[48;5;124m"
        elif color_index == Cube_Color.White:
            text = "\033[107m"
        elif color_index == Cube_Color.Orange:
            text = "\033[48;5;202m"
        elif color_index == Cube_Color.Yellow:
            text = "\033[48;5;11m"
        elif color_index == Cube_Color.Blue:
            text = "\033[48;5;27m"
        elif color_index == Cube_Color.Green:
            text = "\033[102m"
        text += "\033[30m"
        if label:
            text += " {:2} ".format(val)
        else:
            text += "    "
        text += "\033[0m"

        return text

    def __ne__(self, other: Cube) -> bool:
        """
        Check Cube object state inequality to other Cube object.

        Determine if the state of the current Cube is  different from
        another Cube instance by utilizing the equality check.

        :param other: The Cube object to compare against.
        :type other: Cube
        :returns: False if both Cube have the same state, False otherwise.
        :rtype: bool
        """
        return not self.__eq__(other)

    def __eq__(self, other: Cube) -> bool:
        """
        Check Cube object state equality to other Cube object.

        Compare the state of the current Cube with another Cube to determine
        if they are in the same configuration.

        :param other: The Cube object to compare against.
        :type other: Cube
        :returns: True if both Cube have the same state, False otherwise.
        :rtype: bool
        """
        for loop1 in range(54):
            if other.state[loop1] != self.state[loop1]:
                return False
        return True

    def __repr__(self) -> str:
        """
        Convert Cube object to string representation.

        Return a string that represents the current state of the Cube object
        in a JSON-like format, showing the values of each facelet  in the
        cube's state array.

        :returns: A string representation of the Cube object.
        :rtype: str
        """
        # print state
        str_val = '{{ "state" : ['
        for loop1 in range(53):
            str_val += "{}, ".format(self.state[loop1])
        str_val += "{}]}}".format(self.state[53])

        return str_val

    def __str__(self) -> str:
        """
        Convert Cube object to string representation.

        Return a string that visually represents the cube's current state,
        printing each facelet in color. The representation includes the upper
        face, the middle layer, and the bottom face of the cube.

        :returns: A string representation of the Cube in a visual format.
        :rtype: str
        """
        cube_str = ""
        ptr = 0

        # print upper state
        cube_str += "\n"
        for loop1 in range(3):
            cube_str += "            "
            for loop2 in range(3):
                color_index = self.state[ptr + 3 * loop2]
                cube_str += self.print_piece_square(color_index)
            cube_str += "\n"
            ptr += 1

        # print core middle
        ptr = 9
        for loop1 in range(3):
            for loop2 in range(12):
                color_index = self.state[ptr + 3 * loop2]
                cube_str += self.print_piece_square(color_index)
            cube_str += "\n"
            ptr += 1

        # print down
        ptr = 45
        for loop1 in range(3):
            cube_str += "            "
            for loop2 in range(3):
                color_index = self.state[ptr + 3 * loop2]
                cube_str += self.print_piece_square(color_index)
            cube_str += "\n"
            ptr += 1
        cube_str += "\n"

        return cube_str


# -------------------------------------------------
# -------------------------------------------------
# Main HEYKUBE Object
# -------------------------------------------------
# -------------------------------------------------
class heykube:
    """Define the HEYKUBE class.

    Include ability to connect/disconnect from HEYKUBEs
    Program lights and sounds
    Send custom instructions
    Query the cube state, register for moves and notifications
    """

    def __init__(self) -> None:
        """
        heykube class contructor.

        :returns: None
        :rtype: NoneType
        """
        self.cube = Cube()

        # Defines debug level
        self.debug = 0

        # Setup logging
        self.logger = logging.getLogger("heykube")

        # defines connection
        self.connectivity = heykube_btle()

        # setup time step
        self.time_step = 1.0 / 512

        # Initialize BTLE device
        self.notify_queue = self.connectivity.notify_queue
        self.device_name = None

        # Report the states
        self.notify_states = [
            "solution",
            "move",
            "match",
            "double_tap",
            "instruction_empty",
            "instruction_max",
        ]
        self.solution_states = [
            "scrambled",
            "bottom_cross",
            "bottom_layer",
            "middle_layer",
            "top_layer_cross",
            "top_layer_face",
            "top_layer_corner",
            "solved",
        ]
        # mark default last sequence
        self.last_status_seq_num = None

        # patterns
        self.pattern_names = [
            "checkerboard",
            "sixspots",
            "cubeincube",
            "anaconda",
            "tetris",
            "dontcrossline",
            "greenmamba",
            "spiralpattern",
            "python",
            "kilt",
            "cubeincubeincube",
            "orderinchaos",
            "plusminus",
            "displacedmotif",
            "cuaround",
            "verticalstripes",
        ]

    def connect(self, device: BLEDevice) -> bool:
        """
        Connect to a specified Bluetooth Low Energy (BLE) device.

        :param device: A BLEDevice from the bleak library
        :type device: BLEDevice
        :returns: True if the connection was successful, False otherwise.
        :rtype: bool
        """
        # connect
        success = self.connectivity.connect(device)

        # Clear notifications
        self.clear_notify()

        return success

    def disconnect(self) -> bool:
        """
        Disconnect from the currently connected HEYKUBE device.

        :returns: True if the disconnection was successful, False otherwise.
        :rtype: bool
        """
        return self.connectivity.disconnect()

    def get_device(self) -> BLEDevice:
        """
        Scan input args and finds a HEYKUBE for connection.

        Defines the HEYKUBE connection options

        optional arguments:
          -h, --help            show this help message and exit
          --verbose             increase output verbosity
          -n NAME, --name NAME  Directly defines name of a HEYKUBE
                                for connection
          -a ADDRESS, --address ADDRESS
                                Directly defines an HEYKUBE MAC address
                                for connection
          -s, --scan            Scans and reports all the available HEYKUBES
          -d, --debug           Turns on debug prints

        :returns: The connected device
        :rtype: BLEDevice
        """
        # Get the args
        args, _ = self.connectivity.parse_args()

        # Setup debug info
        if args.debug:
            print("Setting logger levels")
            logger.setLevel(logging.INFO)
            self.connectivity.logger.setLevel(logging.INFO)

        # get the device
        device = self.connectivity.get_device(args)

        return device

    def read_cube(self, field: str) -> List[int]:
        """
        Read the value from the specified field and return the response.

        Send a read command for the given field and waits for a response from
        the device. Log the response if received, and time out after 5 seconds
        then return an empty list in case of a timeout.

        :param field: The field to be read from.
        :type field: str
        :returns: The data read from the specified field as a list.
        :rtype: List[int]
        """
        return self.connectivity.read_cube(field)

    def write_cube(
        self, field: str, data: bytes, wait_for_response: bool = True
    ) -> None:
        """
        Send a write command to update the specified field with data.

        Add a write command to the command queue, sending the specified data
        to the given field. The optional parameter determines whether to wait
        for a response after sending the command.

        :param field: The field to which the data will be written.
        :type field: str
        :param data: The data to be written to the field.
        :type data: bytes
        :param wait_for_response: Indicates whether to wait for a response.
        :type wait_for_response: bool, optional
        :returns: None
        :rtype: NoneType
        """
        success = self.connectivity.write_cube(field, data, wait_for_response)
        # TODO for now, make sure command is written before we return
        time.sleep(0.2)
        return success

    # Enable notifications
    def enable_notifications(self, notify_list: list[str]) -> None:
        """
        Register for notifications from HEYKUBE.

        :param notify_list: A list of notification types to subscribe to.
        :type notify_list: list[str]
        """
        if "CubeState" in notify_list:
            self.connectivity.subscribe("CubeState")
        else:
            # arm the notifications
            status_flag = 0
            for loop1, val in enumerate(self.notify_states):
                if val in notify_list:
                    status_flag |= 1 << loop1
            self.write_cube("Status", [status_flag])
            self.connectivity.subscribe("Status")

    def disable_notifications(self) -> None:
        """
        Disable Bluetooth Low Energy notifications from the HEYKUBE device.

        :returns: None
        :rtype: NoneType
        """
        self.connectivity.unsubscribe("CubeState")
        self.connectivity.unsubscribe("Status")

    def wait(self, timeout: int = 10) -> None:
        """
        Wait for specified time.

        :param timeout: Duration to wait in seconds. Default is 10 seconds.
        :type timeout: int
        :returns: None:
        :rtype: NoneType
        """
        start_time = time.time()
        while True:
            current_time = time.time()
            if (current_time - start_time) >= timeout:
                break
            else:
                time.sleep(0.1)

    def wait_for_cube_state(
        self, prev_seq_num: Optional[int] = None, timeout: int = 10
    ) -> Tuple[int, dict]:
        """
        Wait for events from the HEYKUBE.

        Listen for notifications regarding the cube's state and collect move
        information. If the specified timeout elapses without receiving
        an event, the method will exit.

        :param prev_seq_num: The previous sequence number to calculate
                             the number of moves. Defaults to None.
        :type prev_seq_num: Optional[int]
        :param timeout: Specifies the timeout duration in seconds
        :type timeout: int.
        :returns: Number of Moves and a dictionary with notifications events.
        :rtype: Tuple[int, dict]
        """
        status_out = dict()
        num_moves = 0

        # Wait for timeout, keep heartbeart alive
        start_time = time.time()
        while True:
            current_time = time.time()
            if not self.notify_queue.empty():
                status_message = self.notify_queue.get()
                if status_message[0] == "CubeState":
                    self.cube.set_state(status_message[1])
                    logger.info("{} notification".format(status_message[0]))
                    # status_out['cube_state'] = True
                    status_out["seq_num"] = status_message[1][11]
                    status_out["moves"] = Moves()

                    # commpute number of moves
                    if prev_seq_num is None:
                        num_moves = 1
                    else:
                        num_moves = status_out["seq_num"] - prev_seq_num
                        num_moves = num_moves & 0xFF

                    # build the list of new moves
                    index = 42 - num_moves
                    move_list = []
                    for loop1 in range(num_moves):
                        if index & 0x1:
                            next_move = status_message[1][index // 2] >> 4
                            next_move = next_move & 0xF
                        else:
                            next_move = status_message[1][index // 2] & 0xF
                        move_list.append(next_move)
                        index += 1

                    # append the list
                    status_out["moves"].add_moves(move_list)
                    break

            elif (current_time - start_time) >= timeout:
                # cube_state_end = self.read_cube_state()
                break
            else:
                time.sleep(0.1)

        # Parse status bytes
        return num_moves, status_out

    def wait_for_notify(
        self, prev_seq_num: Optional[int] = None, timeout: float = 10
    ) -> tuple[int, dict]:
        """
        Wait for events from the HEYKUBE.

        Listen for notifications from the HEYKUBE device, including status
        updates. A timeout mechanism is included to exit the method if
        no event is received within the specified time.

        :param prev_seq_num: The previous sequence number to calculate the
                            number of moves (default is None).
        :type prev_seq_num: Optional[int]
        :param timeout: Specifies the timeout duration in seconds.
        :type timeout: float
        :returns: Tuple containing the number of new moves and a dict with
                notification events. Returns (0, {}) if nothing was received.
        :rtype: tuple[int, dict]
        """
        status_out = dict()

        # Wait for timeout, keep heartbeart alive
        start_time = time.time()
        while True:
            # Track time
            current_time = time.time()

            # Check the queue
            if not self.notify_queue.empty():
                status_message = self.notify_queue.get()
                if status_message[0] == "Status":
                    status_bytes = status_message[1]
                    status_out = self.parse_status_info(status_bytes[1:6])
                    curr_seq_num = status_out["seq_num"]
                    logger.info(f"Status notification - {status_out}")
                else:
                    status = status_message[0]
                    logger.error(f"Unknown status notification - {status}")
                    cube_state_end = self.read_cube_state()
                    curr_seq_num = cube_state_end["seq_num"]
                    status_out["seq_num"] = cube_state_end["seq_num"]
                    status_out["timestamp"] = cube_state_end["timestamp"]
                break
            elif (current_time - start_time) >= timeout:
                logger.warning("Timeout in the Status notification")
                cube_state_end = self.read_cube_state()
                curr_seq_num = cube_state_end["seq_num"]
                status_out["seq_num"] = cube_state_end["seq_num"]
                status_out["timestamp"] = cube_state_end["timestamp"]
                break
            else:
                time.sleep(0.1)

        # compute number of moves
        if prev_seq_num:
            print("computing moves")
            num_moves = (curr_seq_num - prev_seq_num) & 0xFF
        else:
            num_moves = 0

        # Parse status bytes
        return num_moves, status_out

    def get_notify(self) -> List[str, Any] | None:
        """
        Get the first notification from the queue.

        Check the notification queue for any incoming messages.
        If a message is present, process and return the status or cube state.

        :returns: List of the notification type and its associated data
                if a notification is available, otherwise None.
        :rtype: List[str, Any] | NoneType
        """
        status_out = None
        if not self.notify_queue.empty():
            status_message = self.notify_queue.get()
            if status_message[0] == "Status":
                status_bytes = status_message[1]
                status_out = self.parse_status_info(status_bytes[1:6])
            elif status_message[0] == "CubeState":
                self.cube.set_state(status_message[1])
                status_out = True
            return [status_message[0], status_out]

        return None

    def clear_notify(self) -> None:
        """
        Clear out old notification messages from the queue.

        Remove all notifications currently in the notification queue to
        ensure that only new messages are processed in subsequent operations.

        :returns: None
        :rtype: NoneType
        """
        while not self.notify_queue.empty():
            self.notify_queue.get()

    # ----------------------------------------------------------------------
    # Commands to control the cube
    # ----------------------------------------------------------------------
    def get_pattern_names(self) -> List[str]:
        """
        Return all the pattern names.

        :returns: The list of pattern names.
        :rtype: List[str]
        """
        return self.pattern_names

    def get_pattern_name(self, index: int) -> str:
        """
        Return a pattern name for a given index.

        :param index: A given patter index
        :type index: int
        :returns: A pattern name
        :rtype: str
        """
        return self.pattern_names[index & 0xF]

    # Setup test mode
    def read_moves(
        self, prev_seq_num: Optional[int] = None
    ) -> Dict[str, Union[Moves, float]]:
        """
        Read up to the last 42 moves from the HEYKUBE.

        This method retrieves the move data from the HEYKUBE and processes it
        to form a list of the last moves executed. If a previous sequence
        number is provided, it will filter the moves to include only those
        that occurred after that sequence number.

        :param prev_seq_num: The previous sequence number to
                            filter moves, if provided.
        :type prev_seq_num: Optional[int]
        :returns: A dictionary containing the sequence number, list of moves,
                and the timestamp of the last recorded move.
        :rtype: Dict[str, Union[Moves, float]]
        """
        # Read the moves
        y = self.read_cube("Moves")
        val = dict()
        val["seq_num"] = y[0]
        moves_list = list()
        for loop1 in range(20):
            next_move = y[loop1 + 1] & 0xF
            if next_move != 0xF:
                moves_list.append(next_move)
            next_move = (y[loop1 + 1] >> 4) & 0xF
            if next_move != 0xF:
                moves_list.append(next_move)

        # drop last moves
        if prev_seq_num:
            num_moves = (val["seq_num"] - prev_seq_num) & 0xFF
            moves_list = moves_list[-num_moves:]

        # Form full list
        val["moves"] = Moves()
        val["moves"].add_moves(moves_list)
        val["timestamp"] = (y[21] + (y[22] << 8)) * self.time_step

        return val

    # Setup test mode
    def read_version(self) -> Dict[str, Union[bool, str]]:
        """
        Read the current software version of the HEYKUBE.

        Retrieve the current version information from the HEYKUBE,
        including version number, battery status, motion status, and other
        configurations. Log also relevant information about the HEYKUBE's
        state.

        :returns: A dictionary containing various HEYKUBE information.
        :rtype: Dict[str, Union[bool, str]]
        """
        y = self.read_cube("Version")
        val = dict()

        out_text = "0x"
        for x in y:
            out_text += "{:02x}".format(x)
        logger.info("HEYKUBE version: {}".format(out_text))

        # form the version number
        val["version"] = "v{}.{}".format(y[1], y[0])
        logger.info("HEYKUBE firmware version {}".format(val["version"]))

        # check the accelerometer
        if y[2] & 0x2:
            val["battery"] = True
            logger.info("    Battery voltage in range")
        else:
            val["battery"] = False

        # check the accelerometer
        if y[2] & 0x4:
            val["motion"] = True
            logger.info("    Motion enabled")
        else:
            val["motion"] = False

        # Report the config
        if y[2] & 0x8:
            val["full6"] = True
            logger.info("    FULL6 Moves")
        else:
            val["full6"] = False

        # Report the config
        if y[2] & 0x10:
            val["custom_config"] = True
            logger.info("    Using custom config")
        else:
            val["custom_config"] = False

        # check the hints on/off
        if y[2] & 0x20:
            val["hints"] = False
            logger.info("    Hints off")
        else:
            val["hints"] = True

        # Report BTLE disconnect
        if y[3] in self.connectivity.disconnect_reasons:
            disconnect_reasons = self.connectivity.disconnect_reasons[y[3]]
        else:
            disconnect_reasons = y[3]
        val["disconnect_reason"] = disconnect_reasons

        return val

    def enable_pattern(self, pattern: Union[int, str]) -> None:
        """
        Enable instructions for the pattern if HEYKUBE is solved.

        Enable a visual pattern on the HEYKUBE, which can be specified either
        by its index (integer) or by its name (string). If the HEYKUBE is not
        in a solved state, the pattern will not be enabled.

        :param pattern: The pattern to enable, either as an integer index or
                        a string name. The index must be within the range of
                        available patterns.
        :type pattern: Union[int, str]
        :raises ValueError: If the provided pattern index is out of range or
                            the pattern name is not found.
        :returns: None
        :rtype: NoneType
        """
        # Simulate patterns
        num_patterns = len(self.pattern_names)

        # Get the pattern index
        pattern_index = None
        if isinstance(pattern, int):
            if (pattern < 0) or (pattern >= num_patterns):
                self.logger.error(
                    f"Error, pattern index must be [0,{num_patterns - 1}]"
                )
            else:
                pattern_index = pattern
        else:
            for loop1, val in enumerate(self.pattern_names):
                if pattern == val:
                    pattern_index = loop1
                    break
        # Send the pattern index
        if not (pattern_index is None):
            y = [0x08, pattern_index]
            self.write_cube("Action", y)

    # Read the config back
    def read_config(self) -> List[int]:
        """
        Read the HEYKUBE configuration.

        Retrieve the current configuration settings of the HEYKUBE.
        The configuration data is returned as a list of integers, each
        representing a specific configuration parameter.

        :returns: A list of integers representing the HEYKUBE configuration.
        :rtype: List[int]
        """
        y = self.read_cube("Config")
        if self.debug:
            text = "write_config:"
            for val in y:
                text += " 0x{:02x}".format(val)
            logger.info(text)
        return y

    def enable_match(self) -> None:
        """
        Enable the match to fire again since it disable after each match.

        Re-enable the match functionality in the HEYKUBE. The match feature
        is automatically disabled after each match, and this method allows
        it to be fired again.

        :returns: None
        :rtype: NoneType
        """
        self.write_cube("MatchState", [1])

    def disable_match(self) -> None:
        """
        Disable the match from firing.

        Disable the match feature in the HEYKUBE, preventing it from
        firing until it is explicitly re-enabled.

        :returns: None
        :rtype: NoneType
        """
        self.write_cube("MatchState", [0])

    def set_match(self, match: Match, enable: bool = True) -> None:
        """
        Set the match configuration from the provided Match object.

        Allow the user to define the match settings, specifying whether
        to enable or disable the match.

        :param match: The Match object containing the match settings.
        :type match: Match
        :param enable: Flag to enable or disable the match (default is True).
        :type enable: bool
        :returns: None
        :rtype: NoneType
        """
        data = list()

        # Enable the match
        if enable:
            data.append(1)
        else:
            data.append(0)

        match_list = match.to_list()
        next_byte = 0
        bit_pos = 0
        for loop1, val in enumerate(match_list):
            next_byte |= (val & 0x7) << bit_pos
            bit_pos += 3

            if bit_pos >= 8:
                data.append(next_byte & 0xFF)
                next_byte >>= 8
                bit_pos -= 8
        self.write_cube("MatchState", data)

    def clear_instructions(self) -> None:
        """
        Clear the instructions queue, return to the internal solver.

        Send a command to the HEYKUBE to clear any queued instructions,
        effectively resetting the instruction state.

        :returns: None
        :rtype: NoneType
        """
        self.write_cube("Instructions", [0x0])

    def append_instructions(self, instr_moves: Moves) -> None:
        """
        Append more instructions to the instructions queue.

        Add additional instructions to the existing list of instructions.

        :param instr_moves: A Moves object that holds the list of moves
                            to be appended.
        :type instr_moves: Moves
        :returns: None
        :rtype: NoneType
        """
        self.write_instructions(instr_moves, append=True)

    def write_instructions(
        self, instr_moves: Moves, append: bool = False
    ) -> None:
        """
        Send a custom list of instructions to the HEYKUBE.

        :param instr_moves: A Moves object that holds the moves to be sent.
        :type instr_moves: Moves
        :param append: If True, append instructions to the existing list;
                    otherwise, overwrite the current instructions.
        :type append: bool, optional
        :raises ValueError: If the number of instructions exceeds max limit.
        :returns: None
        :rtype: NoneType
        """
        data = list()
        if len(instr_moves) > 52:
            logger.error("Too many instructions")
            return

        # convert into absolute rotations - TODO
        # Need to add teh X/Y/Y rotations
        # rot_cmd = self.cube.get_absolute_rotations(rot_cmd)
        if len(instr_moves) == 0:
            data.append(0)
            data.append(0xFF)
            logger.info("write_instructions: send empty packet to clear it")
        else:
            logger.info("write_instructions: {}".format(instr_moves))
            data.append(len(instr_moves))
            if append:
                data[0] |= 0x80
            for loop1, move in enumerate(instr_moves):
                val = int(move) & 0xF

                # Todo TODO - translate rotations"
                if (loop1 % 2) == 0:
                    data.append(val)
                else:
                    data[-1] |= val << 4
            if len(instr_moves) & 0x1:
                data[-1] |= 0xF0

        self.write_cube("Instructions", data)

    def read_instructions(self) -> Moves:
        """
        Read out the queued instructions.

        Retrieve the list of rotation instructions from the HEYKUBE and
        process them.

        :returns: Moves containing the list of instructions from queue.
        :rtype: Moves
        """
        y = self.read_cube("Instructions")

        # process instructions
        num_inst = y[0]
        instr_list = list()
        skip = False
        # Read out list of instructions
        index = 1
        for loop1 in range(num_inst):
            # get value
            if loop1 & 0x1:
                val = (y[index] >> 4) & 0xFF
                index += 1
            else:
                val = y[index] & 0xF
            # append to list
            if skip:
                skip = False
            elif (val == 0x7) or (val == 0x6):
                skip = True
            else:
                instr_list.append(val)
        instr = Moves()
        instr.add_moves(instr_list)

        logger.info("instructions: {}".format(instr))
        return instr

    def initialize(self) -> None:
        """
        Reset the internal state back to the solved state.

        Initialize the internal cube state to the solved state,
        send the state to the HEYKUBE, and clear any previous moves.
        Also read the current cube state to ensure synchronization.

        :returns: None
        :rtype: NoneType
        """
        # initialize internal cube state
        cstate = [0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0]

        # Send to the cube
        self.write_cube("CubeState", cstate)

        # Check back and clear previous moves
        self.read_cube_state()
        self.cube.clear_moves()

        if self.debug:
            print(self.cube)

    def is_solved(self) -> bool:
        """
        Check if the HEYKUBE is in the solved state.

        Reads the current cube state and checks if the HEYKUBE is solved.

        :returns: True is the cube is solved; False, otherwise.
        :rtype: bool
        """
        self.read_cube_state()
        return self.cube.is_solved()

    def write_cube_state(self, state: List[int]) -> None:
        """
        Override the internal cube state -- expert only.

        :param state: The state to set for the cube.
        :type state: List[int]
        :returns: None
        :rtype: NoneType
        """
        self.write_cube("CubeState", state)

    def get_seq_num(self) -> int:
        """
        Read the current sequence number from the cube.

        :returns: The current sequence number.
        :rtype: int
        """
        y = self.read_cube("CubeState")
        return int(y[11])

    def get_timestamp(self) -> int:
        """
        Read the current timestamp from the cube.

        :returns: The current timestamp in milliseconds.
        :rtype: int
        """
        y = self.read_cube("CubeState")
        timestamp = (y[21] + (y[22] << 8)) * self.time_step
        return timestamp

    def read_cube_state(self) -> Dict[str, Union[int, Moves]]:
        """
        Read the HEYKUBE state.

        Retrieve the current state of the HEYKUBE, including the sequence
        number, moves made, and the timestamp. Update the internal cube
        state with the information from the cube.

        :returns: A dictionary containing the sequence number, list of moves,
                and the timestamp.
        :rtype: Dict[str, Union[int, Moves]]
        """
        y = self.read_cube("CubeState")
        self.cube.set_state(y)

        # get data from the cube
        val = dict()
        val["seq_num"] = int(y[11])
        moves_list = list()
        for loop1 in range(9):
            next_move = y[loop1 + 12] & 0xF
            if next_move != 0xF:
                moves_list.append(next_move)
            next_move = (y[loop1 + 12] >> 4) & 0xF
            if next_move != 0xF:
                moves_list.append(next_move)
        # Form full list
        val["moves"] = Moves()
        val["moves"].add_moves(moves_list)
        val["timestamp"] = (y[21] + (y[22] << 8)) * self.time_step

        return val

    def read_status(self) -> List[Optional[Dict[str, Any]]]:
        """
        Read up to the last 3 status events registered.

        Retrieve the last three status events from the HEYKUBE and return
        them as a list of dictionaries. If there are fewer than three events,
        only the available events are returned.

        :returns: A list containing up to the last 3 status events,
                    or None if no status events are available.
        :rtype: List[Optional[Dict[str, Any]]]
        """
        # Read the characteristics
        data = self.read_cube("Status")

        # build the output
        status_out_list = list()

        # Check the last three sequence numbers
        for loop1 in range(4):
            # Grab sequence
            list_slice = data[loop1 * 5 + 1 : loop1 * 5 + 6]
            status_out = self.parse_status_info(list_slice)

            if status_out:
                status_out_list.append(status_out)

        return status_out_list

    def read_last_status(self) -> Optional[Dict[str, Any]]:
        """
        Read the last status from the HEYKUBE.

        Retrieve the most recent status event from the HEYKUBE.
        If no status events are available, return None.

        :returns:
            dict or None -- Returns the most recent status event as a
                            dictionary, or None if no status events are
                            available.
        :rtype: Optional[Dict[str, Any]]
        """
        status_out = self.read_status()
        if status_out is None:
            return status_out
        elif isinstance(status_out, list):
            return status_out[0]
        else:
            return status_out

    def read_accel(self) -> Tuple[str, List[float]]:
        """
        Return the cube orientation using the on-board 3D accelerometer.

        Retrieve the current orientation of the cube by reading
        the accelerometer data, along with the 3D acceleration vector.

        :returns: A tuple with the upper face and the acceleration vector.
        :rtype: Tuple[str, List[float]]
        """
        # Read the accelerometer data
        y = self.read_cube("Accel")

        accel_scale = 2.0 / 128.0
        accel_data = list()
        max_index = 0
        for loop1 in range(3):
            val = int(y[loop1])
            if val >= 128:
                val -= 256
            val *= accel_scale
            accel_data.append(val)

            # track max absolute value
            if abs(val) > abs(accel_data[max_index]):
                max_index = loop1

        # get the orientation
        white_yellow = ["White", "Yellow"]
        orange_red = ["Orange", "Red"]
        blue_green = ["Blue", "Green"]
        face_up_set = [white_yellow, orange_red, blue_green]

        max_val = accel_data[max_index]
        if max_val >= 0:
            face_up = face_up_set[max_index][1]
        else:
            face_up = face_up_set[max_index][0]

        return face_up, accel_data

    def calc_battery_capacity(self, batt_voltage: int) -> int:
        """Compute the battery capacity given the battery voltage.

        :returns: The battery capacity
        :rtype: int
        """
        # battery capacity curves
        self.battery_capacity = {
            "volt": [
                3.0,
                3.1,
                3.2,
                3.3,
                3.4,
                3.5,
                3.6,
                3.7,
                3.8,
                3.9,
                4.0,
                4.1,
                4.2,
            ],
            "capacity": [
                0.0,
                0.01,
                0.03,
                0.04,
                0.05,
                0.1,
                0.18,
                0.35,
                0.65,
                0.8,
                0.9,
                0.95,
                1.0,
            ],
        }
        # convert voltage to battery life
        capacity = 0
        if batt_voltage < self.battery_capacity["volt"][0]:
            capacity = self.battery_capacity["capacity"][0]
        elif batt_voltage >= self.battery_capacity["volt"][-1]:
            capacity = self.battery_capacity["capacity"][-1]
        else:
            for loop1 in range(len(self.battery_capacity["volt"]) - 1):
                v0 = self.battery_capacity["volt"][loop1]
                v1 = self.battery_capacity["volt"][loop1 + 1]
                c0 = self.battery_capacity["capacity"][loop1]
                c1 = self.battery_capacity["capacity"][loop1 + 1]

                # compute fit
                if batt_voltage >= v0 and batt_voltage < v1:
                    capacity = (c1 - c0) / (v1 - v0) * (batt_voltage - v0) + c0
                    break
        return int(capacity * 100)

    def read_battery(self) -> Tuple[float | int]:
        """
        Read the battery status and charging state.

        Retrieve the battery voltage and charging status from the HEYKUBE.

        :returns: A tuple containing the battery capacity (float),
                    battery voltage (float), and charging status (int).
        :rtype: Tuple[float, float, int]
        """
        y = self.read_cube("Battery")
        if y[1] & 0x10:
            chrg_status = 1
        else:
            chrg_status = 0

        # voltage is u3.9 format
        batt_voltage = float(y[0] + ((y[1] & 0xF) << 8))
        batt_voltage /= 2.0**9

        # compute capacity
        capacity = self.calc_battery_capacity(batt_voltage)

        return (capacity, batt_voltage, chrg_status)

    def software_reset(self) -> None:
        """
        Issue a software reset through BTLE.

        Send a predefined action sequence to the HEYKUBE to initiate
        a software reset.

        :returns: None
        :rtype: NoneType
        """
        actions = [0x04, 0x00, 0x34, 0x12, 0x45]
        self.write_cube("Action", actions, wait_for_response=False)

    # Sends a hint for the faces
    def send_hint(self, index: int) -> None:
        """
        Play a hint on the faces.

        :param index: Picks one of 6 faces to light up
        :type index: int.
        :returns: None
        :rtype: NoneType
        """
        actions = [0x0B, index]
        self.write_cube("Action", actions)

    # Play sounds
    def play_sound(self, select: int = 0) -> None:
        """
        Play a sound on the HEYKUBE device.

        :param select: Selects the sound index between 0-7
        :type name: int.
        :returns: None
        :rtype: NoneType
        """
        actions = [0x06, select & 0x7]
        self.write_cube("Action", actions)

    def light_led(self, led_index: int) -> None:
        """
        Light one of the LEDs on the cube.

        :param led_index: Picks one of 6 faces to light up
        :type led_index: int
        :returns: None
        :rtype: NoneType
        """
        actions = [0x0D, led_index]
        self.write_cube("Action", actions)

    def turn_off_led(self) -> None:
        """
        Turn off all the LEDs on the HEYKUBE.

        :returns: None
        :rtype: NoneType
        """
        self.light_led(36)

    def flash_all_lights(self) -> None:
        """
        Flash all the LEDs on the HEYKUBE.

        :returns: None
        :rtype: NoneType
        """
        actions = [0x7, 0x6]
        self.write_cube("Action", actions)

    def send_prompt(self, index: int) -> None:
        """
        Flash the LEDs on the HEYKUBE, typically when the cube is solved.

        :param index: The index to determine the LED flash pattern (0-5).
        :type index: int

        :returns: None
        :rtype: NoneType
        """
        actions = [0x7, index % 6]
        self.write_cube("Action", actions)

    # --------------------------------------------------------------
    # Configure the cube
    # --------------------------------------------------------------

    def parse_status_info(self, status_bytes: List[int]) -> HKStatus:
        """
        Parse HEYKUBE status informations.

        Extract relevant status information from the provided list of status
        bytes and return it as a dictionary.

        :param status_bytes: The received status bytes from the HEYKUBE.
        :type status_bytes: List[int]
        :returns: A dictionary containing parsed status information,
                including solution state, sequence number,
                and timestamp.
        :rtype: HKStatus
        """
        # Get the raw dictionary
        status_out = dict()

        # Check first notifaction
        if status_bytes[0] == 0:
            return status_out

        for loop1, field in enumerate(self.notify_states):
            if status_bytes[0] & (1 << loop1):
                status_out[field] = True

        # check solution level and change to levels
        if "solution" in status_out.keys():
            num_correct = status_bytes[1] & 0x3
            solution_index = (status_bytes[1] >> 2) & 0x7
            solution_states = self.solution_states[solution_index]
            # solution = f"{solution_states}:{num_correct}"
            status_out["solution"] = [solution_states, num_correct]

        # reports the sequence number
        status_out["seq_num"] = status_bytes[2]

        # Report timestamp
        timestamp = (status_bytes[3] + (status_bytes[4] << 8)) / 512.0
        status_out["timestamp"] = timestamp

        return status_out

    def turn_hints_off(self) -> None:
        """
        Turn hints off on HEYKUBE - they will return once solved.

        :returns: None
        :rtype: NoneType
        """
        self.write_cube("Action", [0x0A, 0x0])

    def turn_hints_on(self) -> None:
        """Turn HEYKUBE hints back on.

        :returns: None
        :rtype: NoneType
        """
        self.write_cube("Action", [0x09, 0x0])

    def enable_sounds(self, major: bool = True, minor: bool = True) -> None:
        """
        Reenable HEYKUBE sounds if they were previous disables.

        :param major: enables major tone in sound
        :type major: bool
        :param minor: enables minor tone in sound
        :type minor: bool
        :returns: None
        :rtype: NoneType
        """
        y = self.read_config()
        # Switch to instruction mode
        new_config = y[0] & 0xE7
        if major:
            new_config |= 0x8
        if minor:
            new_config |= 0x10
        self.write_config([new_config])

    def disable_sounds(self) -> None:
        """
        Disable the sounds during the BTLE connection session.

        :returns: None
        :rtype: NoneType
        """
        self.enable_sounds(False, False)

    def print_cube(self) -> None:
        """
        Read the current state of HEYKUBE and prints it.

        :returns: None
        :rtype: NoneType
        """
        self.read_cube_state()
        print(self.cube)
