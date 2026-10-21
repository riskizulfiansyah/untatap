//go:build darwin

package main

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/webview/webview_go"
)

func isServerRunning(url string) bool {
	client := http.Client{Timeout: 500 * time.Millisecond}
	resp, err := client.Get(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func main() {
	exePath, err := os.Executable()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get executable path: %v\n", err)
		os.Exit(1)
	}

	// Contents/MacOS -> Contents -> bundle root
	contentsDir := filepath.Dir(filepath.Dir(exePath))
	resourcesDir := filepath.Join(contentsDir, "Resources")

	pythonBin := filepath.Join(resourcesDir, "runtime", "bin", "python3")
	backendScript := filepath.Join(resourcesDir, "backend", "main.py")

	cmd := exec.Command(pythonBin, backendScript)
	cmd.Dir = resourcesDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to start Python backend: %v\n", err)
		os.Exit(1)
	}

	defer func() {
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
	}()

	appURL := "http://127.0.0.1:8767"
	running := false
	for range 40 {
		if isServerRunning(appURL + "/api/ping") {
			running = true
			break
		}
		time.Sleep(250 * time.Millisecond)
	}

	if !running {
		fmt.Fprintf(os.Stderr, "Backend failed to start within timeout\n")
	}

	w := webview.New(true)
	defer w.Destroy()

	w.SetTitle("Tatap")
	w.SetSize(1280, 720, webview.HintNone)
	w.Navigate(appURL)
	w.Run()
}
