import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

// Left click starts/stops the lan-mouse daemon; right click opens the GUI.
BarWidget {
  id: root
  moduleName: "nsitapara.lan-mouse"

  property bool running: false

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refresh() {
    if (!checkProc.running) checkProc.running = true
  }

  function toggle() {
    if (root.running) root.bar.run("pkill -x lan-mouse")
    else root.bar.run("setsid -f lan-mouse daemon >/dev/null 2>&1")
    root.running = !root.running
    recheck.restart()
  }

  Process {
    id: checkProc
    command: ["pgrep", "-f", "^lan-mouse daemon"]
    onExited: function(exitCode) {
      root.running = exitCode === 0
    }
  }

  Timer {
    interval: 5000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    id: recheck
    interval: 1000
    onTriggered: root.refresh()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.running ? "󰍽" : "󰍾"
    active: root.running
    opacity: root.running ? 1 : 0.5
    tooltipText: root.running ? "Lan Mouse on — click to stop" : "Lan Mouse off — click to start"
    onPressed: function(b) {
      if (b === Qt.RightButton) root.bar.run("pkill -x lan-mouse; setsid -f lan-mouse >/dev/null 2>&1")
      else root.toggle()
    }
  }
}
