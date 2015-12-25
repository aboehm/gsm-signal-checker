#!/usr/bin/python
# coding=utf8
# vi: autoindent noexpandtab tabstop=4 shiftwidth=4
#
# gsmchecker - A signal strength meter for gsm modems
# Copyright (c) 2015, Alexander Böhm
# 
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import sys, serial, traceback, datetime, gobject, json
from optparse import OptionParser, OptionGroup
import json

class ATTermSession:
	def __init__(self, device, baudrate=9600, timeout=0.1):
		self.device = device
		self.baudrate = baudrate
		self.timeout = timeout

	def execute(self, command):
		modem = serial.Serial(self.device, self.baudrate, timeout=self.timeout)
		modem.write(("%s\r" % (command)).encode())
		modem.flush()
		at_resp = modem.read(1024)
		at_resp = at_resp.split('\r\n')
		modem.close()
		return at_resp

	def getDevice(self):
		return self.device

class AT_Command:
	def __init__(self, session, command="AT"):
		self.session = session
		self.command = command

	def run(self, options=""):
		return self.session.execute("%s%s" % (self.command, options))

class AT_CSQ(AT_Command):
	def __init__(self, session):
		AT_Command.__init__(self, session, "AT+CSQ")
		self.signal_strength = None
		self.signal_rssi = None
		self.signal_assessment = None
		self.signal_time = datetime.datetime.now()
		self.changeHandler = None
		self.createSignal2RssiTable()

	def createSignal2RssiTable(self):
		self.sig2rssi_table = 31*[0]

		for i in range(1, 31):
			if i == 0:
				self.sig2rssi_table[i] = -113
			elif i == 7:
				self.sig2rssi_table[i] = -99
			else:
				self.sig2rssi_table[i] = self.sig2rssi_table[i-1]+2

	def assessSignalQuality(self):
		# src: http://m2msupport.net/m2msupport/atcsq-signal-quality/
		if self.signal_strength < 2:
				self.signal_assessment = "None"
		elif self.signal_strength >= 2:
				self.signal_assessment = "Marginal"
		elif self.signal_strength >= 10:
				self.signal_assessment = "OK"
		elif self.signal_strength >= 15:
				self.signal_assessment = "Good"
		elif self.signal_strength >= 20:
				self.signal_assessment = "Excellent"
				
		if self.signal_strength < 1:
				self.signal_rssi = "< -113 dBm"
		elif self.signal_strength >= 1 and self.signal_strength <= 30:
				self.signal_rssi = "%i dBm" % (self.sig2rssi_table[int(self.signal_strength)])
		elif self.signal_strength > 30:
				self.signal_rssi = "> -51 dBm"

	def updateSignal(self):
		at_resp = self.run()
		if at_resp == None:
			s = self.getSignal()
			self.changeHandler(s)
			return s
		else:
			self.signal_time = datetime.datetime.now()

		old_signal = self.signal_strength
		ss = None

		for i in at_resp:
			if i.find('+CSQ: ') >= 0:
				ss = i.split(': ')[1]
				self.signal_strength = float(ss.replace(",", "."))

		if ss == None:
			s = self.getSignal()
			self.changeHandler(s)
			return s

		if self.signal_strength != None:
			self.assessSignalQuality()
		else:
			self.signal_rssi = None
			self.signal_assessment = None

		s = self.getSignal()

		if self.signal_strength != old_signal:
			if self.changeHandler != None:
				self.changeHandler(s)

		return s

	def getSignal(self):
		return {
				"device": self.session.getDevice(),
				"strength": self.signal_strength,
				"rssi": self.signal_rssi,
				"assessment": self.signal_assessment,
				"time": self.signal_time,
		}

	def setChangeHandler(self, handler):
		self.changeHandler = handler

class SignalService:
	def __init__(self, session, interval=60):
		self.running = False
		self.atcsq = AT_CSQ(session)
		self.atcsq.setChangeHandler(self.onSignalChange)
		self.interval = interval

	def start(self):
		self.running = True
		gobject.timeout_add(self.interval*1000, self.onUpdate)
		self.onUpdate()

	def stop(self):
		self.running = False

	def update(self):
		try:
			r = self.atcsq.updateSignal()
		except KeyboardInterrupt as e:
			self.running = False
		except Exception as e:
			print("Exception while signal check: %s" % (e))
			traceback.print_exc(file=sys.stdout)
			self.running = False

	def onUpdate(self):
		self.update()

		if self.running:
			return True
		else:
			return False

	def isRunning(self):
		return self.running

	def onSignalChange(self, signal):
		None

	def setChangeHandler(self, handler=None):
		if handler == None:
			self.atcsq.setChangeHandler(self.onSignalChange)
		else:
			self.atcsq.setChangeHandler(handler)

	def stop(self):
		self.running = False

class TraySignalService(SignalService):
	mappings = {
			None: "/usr/share/icons/Adwaita/64x64/status/network-cellular-signal-none-symbolic.symbolic.png",
			"Marginal": "/usr/share/icons/Adwaita/64x64/status/network-cellular-signal-weak-symbolic.symbolic.png",
			"OK": "/usr/share/icons/Adwaita/64x64/status/network-cellular-signal-ok-symbolic.symbolic.png",
			"Good": "/usr/share/icons/Adwaita/64x64/status/network-cellular-signal-good-symbolic.symbolic.png",
			"Excellent": "/usr/share/icons/Adwaita/64x64/status/network-cellular-signal-excellent-symbolic.symbolic.png",
	}

	def __init__(self, session, interval=60):
		SignalService.__init__(self, session, interval)
		self.symbol = gtk.status_icon_new_from_file(TraySignalService.mappings[None])
		self.symbol.set_tooltip('Waiting for information')
		self.symbol.connect('popup-menu', self.onRightClick)

	def start(self):
		SignalService.start(self)
		gtk.main()

	def close(self, data=None):
		gtk.main_quit()

	def makeMenu(self, button, time, data=None):
		menu = gtk.Menu()
		close_item = gtk.MenuItem("Close")
		close_item.connect_object("activate", self.close, "Close")
		menu.append(close_item)
		close_item.show()
		menu.popup(None, None, None, button, time)

	def onRightClick(self, data, button, time):
		self.makeMenu(button, time)

	def onSignalChange(self, signal):
		if signal == None:
			self.symbol.set_from_file(TraySignalService.mappings[None])
			self.symbol.set_tooltip("Unknown")
		else:
			self.symbol.set_from_file(TraySignalService.mappings[signal["assessment"]])
			self.symbol.set_tooltip("RSSI dBm: %s\nStrength: %f\nAssesment: %s" % (signal["rssi"], signal["strength"], signal["assessment"]))

	def update(self):
		try:
			return self.atcsq.updateSignal()

		except Exception as e:
			print("Exception while signal check: %s" % (e))
			self.running = False
			return None

	def run(self):
		None

def printSignalChange(signal):
	print("%s: Signal strength %i (%s), RSSI %s" % (signal["time"], signal["strength"], signal["assessment"], signal["rssi"]))

def printJsonSignalChange(signal):
	r = {
			"time": signal["time"].isoformat(),
			"strength": signal["strength"],
			"assessment": signal["assessment"],
			"rssi": signal["rssi"],
	}
	print(json.dumps(r))

if __name__ == "__main__":
	p = OptionParser(usage="usage: %prog [options] <modem>", version="0.1", description="A signal strength checker for GSM modem")
	p.add_option("-t", action="store_true", dest="textmode", default=False, help="show signal strength as text")
	p.add_option("-g", action="store_false", dest="textmode", help="show signal strength as an tray icon (requires GTK)")
	p.add_option("-i", type="int", default=60, dest="interval", help="interval in seconds between checks (default 60 seconds)")

	g = OptionGroup(p, "Text mode options")
	g.add_option("-o", "--once", action="store_true", default=False, help="check signal one time")
	g.add_option("-j", "--json", action="store_true", default=False, help="output format is json")
	p.add_option_group(g)
	(options, args) = p.parse_args()

	if len(args) != 1:
		p.error("you need a modem device as argument")
	else:
		atsrv = ATTermSession(args[0])

	if not options.textmode:
		try:
			import gtk
		except:
			p.error("request GUI mode not available. Check your pyGTK installation")

	if (options.once or options.json) and not options.textmode:
		p.error("running once or json output only available in text mode")

	if options.textmode:
		ss = SignalService(atsrv, interval=options.interval)

		if options.json:
			ss.setChangeHandler(printJsonSignalChange)

		else:
			ss.setChangeHandler(printSignalChange)

	else:
		ss = TraySignalService(atsrv, interval=options.interval)

	if options.once:
		ss.update()

	else:
		ss.start()
		try:
			if options.textmode:
				gobject.MainLoop().run()
			else:
				gtk.main()

		except KeyboardInterrupt:
			pass

		sys.exit()
