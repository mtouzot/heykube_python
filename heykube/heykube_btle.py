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
"""
Create a HEYKUBE BTLE connectivity class.

Classes:
    heykube_btle
"""
from typing import List, Optional, Union
from queue import Queue
import time
import threading
import asyncio
import re
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
import logging
import argparse

# -------------------------------------------------
# -------------------------------------------------
# Defines wireless connectivity
# -------------------------------------------------
# -------------------------------------------------


# HEYKUBE connectivity class
class heykube_btle:
    """
    This class manage HEYKUBE BTLE connectivity using Bleak module.

    Extend the :class:`heykube` class.

    :ivar logger: object's prompt logger named `heykube_btle`
    :type logger: Logger
    :ivar client: Bleak Client to manage Bluetooth Low Energy devices
    :type client: BleakClient
    :ivar connected: Device connection status
    :type connected: bool
    :ivar disconnected: Device disconnection status
    :type disconnected: bool
    :ivar reconnected: Device reconnection status
    :type reconnected: bool
    :ivar connected_device: connected Bluetooth Low Energy device
    :type connected_device: BLEDevice
    :ivar cmd_queue: Queue to manage commands
    :type cmd_queue: Queue
    :ivar read_queue:
    :type read_queue: Queue
    :ivar notify_queue:
    :type notify_queue: Queue
    :ivar device: NOT USED
    :type device: NoneType
    :ivar addr: NOT USED
    :type addr: NoneType
    :ivar heykube_uuid: Device UUID
    :type heykube_uuid: str
    :ivar char_uuid: Characterics UUID
    :type char_uuid: Dict[str, str]
    :ivar char_handles: Notifications to handle
    :type char_handles: Dict[int, str]
    :ivar disconnect_reasons: Reason of device disconnection
    :type disconnect_reasons: Dict[bytes, str]
    :ivar scan_devices: List of scanned devices
    :type scan_devices: List[str]
    :ivar loop: event loop to manage Bluetooth and set up the BLEAK client
    :type loop: asyncio.new_event_loop()
    """

    client: BleakClient = None

    def __init__(self) -> None:
        """
        heykube_btle class constructor.

        Set up logging, initialize device state, create queues for command,
        read, and notification handling, and configures the UUIDs for
        various characteristics related to the HEYKUBE device.
        Define common Bluetooth disconnect reasons.

        :returns: None
        :rtype: NoneType
        """
        self.logger = logging.getLogger("heykube_btle")
        self.logger.info("Initializing HEYKUBE BTLE class")

        # Device state
        self.connected = False
        self.connected_device = None

        # Setup multiple queues
        self.cmd_queue = Queue()
        self.read_queue = Queue()
        self.notify_queue = Queue()

        # clear the device
        self.device = None
        self.addr = None

        # Setup device UUID
        self.heykube_uuid = "b46a791a-8273-4fc1-9e67-94d3dc2aac1c"
        self.char_uuid = {
            "Version": "5b9009f6-03bf-41aa-87fc-582d8b2bd6b9",
            "Battery": "fd51b3ba-99c7-49c6-9f85-5644ff56a378",
            "Config": "f0ac8d24-6daf-4f47-9953-fd921da215e1",
            "CubeState": "a2f41a4e-0e31-4bbc-9389-4253475481fb",
            "Status": "9bbc2d67-0ba7-4440-aedf-08fb019687f9",
            "MatchState": "982af399-ef78-4eff-b24d-2e1a01aa9f13",
            "Instructions": "1379570d-86c6-45a4-8778-f552e7feb290",
            "Action": "e06da2b8-c643-42b1-895b-a5acbbf30afd",
            "Accel": "272a1fe9-058b-402b-8298-7fec5ce7473e",
            "Moves": "F2FF5401-2BC0-415B-A2F1-6549D6CA0AD8",
        }

        self.char_handles = {24: "Status", 19: "CubeState"}

        # set BTLE disconnect reasons
        self.disconnect_reasons = {
            0x13: "Remote User Terminated Connection",
            0x10: "Connection Accept Timeout Exceeded",
            0x08: "Connection timeout",
        }

    # ---------------------------------------------------
    # Public interface
    # --------------------------------------------------
    def parse_args(self) -> tuple:
        """
        Parse command line arguments for the HEYKUBE connection interface.

        Set up an argument parser for the HEYKUBE connection options,
        including verbosity, device name, address, scanning, debugging,
        and devboard mode. Return the parsed arguments and any unknown
        arguments provided during execution.

        :returns: A tuple containing the known and unknown arguments.
        :rtype: tuple
        """
        parser = argparse.ArgumentParser(
            description="Defines the HEYKUBE connection options"
        )
        parser.add_argument(
            "--verbose", help="increase output verbosity", action="store_true"
        )
        # 4 different options
        parser.add_argument(
            "-n",
            "--name",
            action="store",
            help="Directly defines name of a HEYKUBE for connection",
            type=str,
        )
        parser.add_argument(
            "-a",
            "--address",
            action="store",
            help="Directly defines an HEYKUBE MAC address for connection",
            type=str,
        )
        parser.add_argument(
            "-s",
            "--scan",
            help="Scans and reports all the available HEYKUBES",
            action="store_true",
        )
        parser.add_argument(
            "-d", "--debug", action="store_true", help="Turns on debug prints"
        )
        parser.add_argument(
            "--dev-board",
            action="store_true",
            help="Turns on the devboard mode with external user input",
        )

        # return parser.parse_args()
        return parser.parse_known_args()

    def scan(self, timeout: float = 5.0) -> List[str]:
        """
        Scan for available HEYKUBE devices.

        Initiates a scan for HEYKUBE devices and runs the scan for the
        specified timeout period. Return a list of devices discovered during
        the scan.

        :param timeout: The duration for which the scan will run, in seconds.
                        Default is 5.0 seconds.
        :type timeout: float
        :returns: A list of discovered HEYKUBE devices.
        :rtype: List[str]
        """
        # Run the loop for 5 seconds
        scan_loop = asyncio.new_event_loop()
        scan_loop.run_until_complete(self.scan_run())

        return self.scan_devices

    def is_connected(self) -> bool:
        """
        Return the client's connection status.

        Check if the client is currently connected and returns a boolean
        indicating the connection status.

        :returns: The connection status of the client.
        :rtype: bool
        """
        if self.client:
            return True
        else:
            return False

    def get_device(self, args) -> Optional[BLEDevice]:
        """
        Retrieve the device object based on the input arguments provided.

        Scan for available HEYKUBE devices and returns the matching
        device based on the provided arguments, such as name or address.
        If no matching device is found, log warnings or prompts user to wake up
        the devices.

        :param args: Arguments used to specify the HEYKUBE device.
        :type args: argparse.Namespace
        :returns: The connected device object or None if not found.
        :rtype: BLEDevice or None
        """
        # Find the device
        connected_device = None

        # Run the scan
        scan_devices = self.scan()

        # Scan for HEYKUBES
        if args.scan or (args.name is None and args.address is None):
            if len(scan_devices) == 0:
                print(
                    """Did not find any HEYKUBEs, """
                    """wakeup them up by moving them"""
                )
                print("")
                print("You can check for previously connected devics")
                print("# check for connected devices")
                print("hcitool conn")
                print("")
                print("# disconnect them if needed")
                print("hcitool ledc 64")
            for device in scan_devices:
                print(
                    "    {} : addr {} at {} dB RSSI".format(
                        device.name, device.address, device.rssi
                    )
                )

        # Match name
        if args.name:
            for device in scan_devices:
                if args.name == device.name:
                    connected_device = device
                    break
            if connected_device is None:
                self.logger.warning(
                    f"""Did not find {args.name} - make sure it is close by"""
                    """ and turn a face to enable bluetooth"""
                )

        # Match address
        elif args.address:
            for device in scan_devices:
                if args.address == device.address:
                    connected_device = device
                    break
            if connected_device is None:
                self.logger.warning(
                    f"""Did not find {args.name} - make sure it is close by"""
                    """ and turn a face to enable bluetooth"""
                )

        # Connect to the first one
        elif not args.scan:
            if len(scan_devices) > 0:
                connected_device = scan_devices[0]

        return connected_device

    def connect(self, device: BLEDevice, timeout: int = 10) -> bool:
        """Connect to a HEYKUBE.

        :param device: HEYKUBE device
        :type device: keykube
        :param timeout: connection time-out in seconds
        :param timeout: float
        :returns: The connection status, True if connected, False otherwise.
        :rtype: bool
        """
        # Start the thread to connect
        self.logger.info("Starting thread")
        self.thread = threading.Thread(
            target=self.connection_thread, args=(device,)
        )
        self.thread.start()

        # Wait for connection
        start_time = time.time()
        while True:
            if not self.read_queue.empty():
                read_resp = self.read_queue.get()
                # print('read_resp ', read_resp)
                self.logger.info("read_resp {}".format(read_resp))
                if read_resp[0] == "connected":
                    return True

            # timeout
            elif (time.time() - start_time) >= timeout:
                self.disconnect()
                while not self.read_queue.empty():
                    self.read_queue.get()
                self.logger.error(
                    f"Timeout in connection after {timeout}s, disconnecting"
                )
                return False

    def disconnect(self) -> None:
        """
        Disconnect from the BTLE client and terminate the connection thread.

        Send a disconnect command to the command queue and waits for the
        connection thread to finish. It also logs the disconnection status and
        confirms when the thread has successfully ended.

        :returns: None
        :rtype: NoneType
        """
        # send the disconnect command
        self.cmd_queue.put(["disconnect"])

        # print('Waiting for connection thread to finish')
        self.logger.info("Waiting for connection thread to finish")
        self.thread.join()
        self.logger.info("Done with thread")

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
        # read the characteristics
        start_time = time.time()

        # send the disconnect command
        self.cmd_queue.put(["read", field])

        while True:
            if not self.read_queue.empty():
                read_resp = self.read_queue.get()
                self.logger.info(f"read_resp {read_resp}")
                if read_resp[0] == "read":
                    return list(read_resp[1])
            elif (time.time() - start_time) >= 5.0:
                self.logger.error("ERROR timeout in cube read")
                return list()

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
        # send the disconnect command
        self.cmd_queue.put(["write", field, data])

    def unsubscribe(self, field: str) -> None:
        """
        Unsubscribe from notifications for a specified field.

        Add an unsubscribe command to the command queue, indicating that
        notifications for the specified field should no longer be received.

        :param field: The field from which notifications will be unsubscribed.
        :type field: str
        :returns: None
        :rtype: NoneType
        """
        self.cmd_queue.put(["unsubscribe", field])

    def subscribe(self, field: str) -> None:
        """
        Subscribe to notifications for a specified field.

        Add a subscribe command to the command queue, indicating that
        notifications should be received for the specified field.

        :param field: The field to which notifications will be subscribed.
        :type field: str
        :returns: None
        :rtype: NoneType
        """
        self.cmd_queue.put(["subscribe", field])

    # ---------------------------------------------------
    # Internal code
    # --------------------------------------------------
    def on_disconnect(self, client: BleakClient):
        """
        Handle disconnection from the Bluetooth device.

        Invoked when the BLEAK client is disconnected from the HEYKUBE device.
        Set the connection status to False and print a message indicating
        the disconnection.

        :param client: The BLEAK client instance that has disconnected.
        :type client: BleakClient
        :returns: None
        :rtype: NoneType
        """
        self.connected = False
        print("Disconnected from HEYKUBE")

    def connection_thread(self, device: BLEDevice) -> None:
        """
        Establish a connection to a specified Bluetooth device.

        Create a new event loop for managing Bluetooth connections and
        set up the BLEAK client. Start both the connection manager and
        communication manager concurrently and run  until they complete.
        After the connection process is finished, log the closure
        of the connection and clears the command queue.

        :param device: The Bluetooth device to connect to.
        :type device: BLEDevice
        :returns: None
        :rtype: NoneType
        """
        # Get a new loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # setup BLEAK client
        self.client = BleakClient(device.address, loop=self.loop)
        self.connected = False
        self.reconnected = False
        self.disconnected = False

        # run the connections manager
        futures = asyncio.gather(
            self.connection_manager(), self.comms_manager()
        )

        # Run til they are complete
        self.loop.run_until_complete(futures)
        self.logger.info("Closing out the connection")
        self.loop.close()

        # Clear the command queue
        while not self.cmd_queue.empty():
            self.cmd_queue.get()

    async def connection_manager(self) -> None:
        """
        Manage the connection to the HEYKUBE device.

        Monitor continuously the connection status. If disconnected, attempt
        a reconnection to the HEYKUBE device. Keep track of connection retries
        and log relevant events. Handle the first connection separately from
        reconnections to ensure appropriate notifications are sent.

        :returns: None
        :rtype: NoneType
        """
        connection_retries = 0
        first_connection = True

        # ------------------------------------------
        # Keep the connection going
        # ------------------------------------------
        while True:
            # ------------------------------------------------
            # Keep connection running
            # ------------------------------------------------
            if self.disconnected:
                return
            elif self.connected:
                await asyncio.sleep(0.1, loop=self.loop)
            # ------------------------------------------------
            # Bail-out for disconnect
            # ------------------------------------------------
            # elif self.client is None:
            #    return
            # -------------------------------------------------
            # Keep establishing the connection
            # -------------------------------------------------
            else:
                try:
                    # get the connection
                    await self.client.connect()
                    # self.connected = await self.client.is_connected()
                    self.connected = self.client.is_connected

                    # Check if connected
                    if self.connected:
                        self.logger.info("Connected to {}".format(self.client))
                        connection_retries = 0
                        self.client.set_disconnected_callback(
                            self.on_disconnect
                        )

                        # First connection
                        if first_connection:
                            self.read_queue.put(["connected"])
                            first_connection = False
                        else:
                            self.reconnected = True
                    else:
                        connection_retries += 1
                        self.logger.error(
                            "Failed to connect to {}".format(self.client)
                        )
                except Exception as e:
                    self.logger.error(
                        "connection_manager exception: {}".format(e)
                    )
                    self.logger.error("Trying to reconnect to HEYKUBE")

                    if connection_retries >= 3:
                        self.logger.error(
                            "connection_manager exception: {}".format(e)
                        )
                        return

    async def comms_manager(self) -> None:
        """
        Manage communication with HEYKUBE devices.

        Checks continuously for commands related to connecting, reading,
        writing, subscribing, and unsubscribing to characteristics of
        the HEYKUBE devices.
        Handle reconnection, logging events, and ensuring communication
        integrity.

        The following commands can be processed:
        - "disconnect": Disconnects the client from the device.
        - "read": Reads characteristics from the device.
        - "write": Writes data to the device.
        - "subscribe": Subscribes to notifications from the device.
        - "unsubscribe": Unsubscribes from notifications from the device.

        :returns: None
        :rtype: NoneType
        """
        num_tries = 0
        cmd = [None, None]
        notify_list = list()

        # -------------------------------------------------
        # Run the connection
        # -------------------------------------------------
        while True:
            # Run theh command
            if self.connected:
                # Check if we get a new command
                if cmd[0] is None:
                    if not self.cmd_queue.empty():
                        cmd = self.cmd_queue.get()
                        self.logger.info("Testing {}".format(cmd))
                        num_tries += 1

                # -------------------------------------
                # Reconnect subscription
                # -------------------------------------
                if self.reconnected:
                    for UUID in notify_list:
                        try:
                            await self.client.start_notify(
                                UUID, self.notification_handler
                            )
                            self.reconnected = False
                        except Exception as e:
                            self.logger.exception(
                                "comms_manager::resubscribe Failure"
                            )
                            print(e)

                # -------------------------------------
                # Disconnect
                # -------------------------------------
                if cmd[0] == "disconnect":
                    self.disconnected = True
                    await self.client.disconnect()
                    self.client = None
                    self.logger.info("Done with disconnect")
                    return

                # -------------------------------------
                # Read characteristics
                # -------------------------------------
                elif cmd[0] == "read":
                    UUID = self.char_uuid[cmd[1]]
                    self.logger.info("Reading from {}".format(cmd[1]))

                    read_bytes = list()
                    try:
                        read_bytes = await self.client.read_gatt_char(UUID)

                        # success
                        if len(read_bytes) > 0:
                            cmd[0] = None
                            num_tries = 0
                            self.logger.info(
                                "Sending bytes {}".format(read_bytes)
                            )
                            self.read_queue.put(["read", read_bytes])
                        else:
                            self.logger.error(
                                "WHY AM I HERE -- Read did not fail correctly"
                            )

                    except Exception as e:
                        self.logger.exception("comms_manager::Read Failure")
                        print(e)
                # -------------------------------------
                # Write characteristics
                # -------------------------------------
                elif cmd[0] == "write":
                    # Setup data
                    UUID = self.char_uuid[cmd[1]]
                    bytes_to_send = bytearray(cmd[2])

                    self.logger.info("Writing to {}".format(cmd[1]))
                    try:
                        response = False
                        await self.client.write_gatt_char(
                            UUID, bytes_to_send, response=response
                        )
                        cmd[0] = None
                        num_tries = 0
                        if response:
                            self.logger.info("Done with write")
                    except Exception as e:
                        self.logger.exception("comms_manager::Write Failure")
                        print(e)

                # -------------------------------------
                # Subscribe to characteristics
                # -------------------------------------
                elif cmd[0] == "subscribe":
                    UUID = self.char_uuid[cmd[1]]

                    if UUID in notify_list:
                        self.logger.warning(
                            "Already subscribed to {}".format(cmd[1])
                        )
                        num_tries = 0
                        cmd[0] = None
                    else:
                        try:
                            await self.client.start_notify(
                                UUID, self.notification_handler
                            )
                            num_tries = 0
                            cmd[0] = None
                            notify_list.append(UUID)
                        except Exception as e:
                            self.logger.error(
                                "subscribe Failure with {}".format(e)
                            )

                # -------------------------------------
                # Unsubscribe if written
                # -------------------------------------
                elif cmd[0] == "unsubscribe":
                    UUID = self.char_uuid[cmd[1]]

                    # handle unsubcribe
                    if UUID in notify_list:
                        try:
                            self.logger.info(
                                "unsubscribe from {}".format(cmd[1])
                            )
                            await self.client.stop_notify(UUID)
                            num_tries = 0
                            cmd[0] = None
                            notify_list.remove(UUID)
                        except Exception as e:
                            self.logger.exception(
                                "comms_manager::unsubscribe Failure"
                            )
                            print(e)
                    # ignore the command
                    else:
                        num_tries = 0
                        cmd[0] = None

                # ------------------------------------
                # wait for next command
                # ------------------------------------
                else:
                    await asyncio.sleep(0.1, loop=self.loop)

            # ------------------------------------
            # wait for reconnection
            # ------------------------------------
            else:
                await asyncio.sleep(0.1, loop=self.loop)

    async def cleanup(self) -> None:
        """
        Clean up resources and disconnect the client if connected.

        Log a cleanup message and disconnects the client from any active
        connections if the client is initialized.

        :returns: None
        :rtype: NoneType
        """
        self.logger.info("Cleaning up")
        if self.client:
            await self.client.disconnect()

    async def scan_run(self) -> None:
        """
        Perform an asynchronous BTLE scan for available HEYKUBE devices.

        Clear any previously scanned devices and discover new devices using
        the BleakScanner. Log the name, address, and RSSI of HEYKUBE devices
        found during the scan.

        :returns: None
        :rtype: NoneType
        """
        # Clear previous devices
        self.scan_devices = list()

        all_devices = await BleakScanner.discover()
        for device in all_devices:
            if "HEYKUBE" in device.name:
                # print(
                #     "Found {}({}) at {} dB RSSI".format(
                #         device.name, device.address, device.rssi
                #         )
                # )
                self.logger.info(
                    "Found {}({}) at {} dB RSSI".format(
                        device.name, device.address, device.rssi
                    )
                )
                self.scan_devices.append(device)

    def notification_handler(
        self, sender: Union[str, int], data: Union[list, bytearray]
    ) -> None:
        """
        Handle notifications from the Heykube BTLE device.

        Invoked when a notification is received from the device.
        Process the notification by determining the sender and placing the
        data in a queue for further processing.
        If the sender is part of the known characteristic handles, associate
        the data with the corresponding field.

        :param sender: The notification sender's identifier, which can be a
                    string or an integer. If a string, it attempts to extract a
                    hexadecimal characteristic ID.
        :type sender: str or int
        :param data: Data received in the notification, typically a byte array.
        :type data: bytes or list
        :raises Exception: If an error occurs while processing,
                        log the exception and handles the error gracefully.
        :returns: None
        :rtype: NoneType
        """
        try:
            self.logger.info("Notification from {}".format(sender))

            # Handle both int and characteristics list
            sender_id = 0
            if isinstance(sender, int):
                sender_id = sender
            else:
                m = re.search("service000c/char([0-9A-Fa-f]+)", sender)
                if m:
                    sender_id = int(m.group(1), 16)
                    self.logger.info(f"Convert notification to {sender_id}")

            # if sender == 20 or sender == 19:
            if sender_id in self.char_handles:
                field = self.char_handles[sender_id]
                self.notify_queue.put([field, list(data)])

        except Exception:
            self.logger.exception("Bad notification from {}".format(sender))
