;;; coil-live.el --- Native Coil live programming over nREPL -*- lexical-binding: t; -*-

;; This uses nREPL as transport, but deliberately does not pretend Coil is
;; Clojure. Coil-specific operations and diagnostics stay explicit.

(require 'cl-lib)
(require 'nrepl-client)
;; The major mode itself lives in the coil repo (src/tooling/editors/emacs).
;; coil-live only adds commands on top of it; it must never define its own
;; `coil-mode', or it silently replaces the real one and takes font-lock,
;; indentation and imenu with it.
(require 'coil-mode)

(defgroup coil-live nil "Live Coil development." :group 'languages)

(defcustom coil-live-port-file ".nrepl-port"
  "Project-relative port file written by coil-live-nrepl."
  :type 'string)

(defvar-local coil-live-connection nil)
(defvar coil-live-connections (make-hash-table :test #'equal)
  "Live nREPL connection buffers keyed by project, host, and port.")
(defvar coil-live-last-state nil)

(defun coil-live--project-root ()
  (or (locate-dominating-file default-directory "Coil.toml")
      default-directory))

(defun coil-live-connect (&optional host port)
  "Connect this buffer to the project live runtime."
  (interactive)
  (let* ((root (coil-live--project-root))
         (port-file (expand-file-name coil-live-port-file root))
         (port (or port
                   (and (file-readable-p port-file)
                        (string-to-number
                         (string-trim
                          (with-temp-buffer
                            (insert-file-contents port-file)
                            (buffer-string)))))
                   (read-number "Coil nREPL port: ")))
         (host (or host "127.0.0.1"))
         (key (list (file-truename root) host port))
         (shared (gethash key coil-live-connections)))
    (unless (and (buffer-live-p shared)
                 (process-live-p (get-buffer-process shared)))
      (setq shared
            (process-buffer
             (nrepl-start-client-process
              host port nil
              (lambda (_endpoint)
                (generate-new-buffer
                 (format " *coil-live %s:%d*" host port))))))
      (puthash key shared coil-live-connections))
    (setq coil-live-connection shared)
    (message "Connected to Coil live runtime on %s:%d" host port)))

(defun coil-live--connection ()
  (or (and coil-live-connection
           (buffer-live-p coil-live-connection)
           (process-live-p (get-buffer-process coil-live-connection))
           coil-live-connection)
      (progn (call-interactively #'coil-live-connect) coil-live-connection)))

(defun coil-live--show-error (response)
  (let ((diagnostic (or (nrepl-dict-get response "err") "Coil edit failed")))
    (with-current-buffer (get-buffer-create "*coil-diagnostics*")
      (let ((inhibit-read-only t))
        (erase-buffer)
        (insert diagnostic)
        (compilation-mode)
        (display-buffer (current-buffer))))))

(defun coil-live--handler (origin)
  (lambda (response)
    (cond
     ((nrepl-dict-get response "err") (coil-live--show-error response))
     ((nrepl-dict-get response "value")
      (setq coil-live-last-state (nrepl-dict-get response "value"))
      (message "Coil edit committed")))
    (when (member "done" (nrepl-dict-get response "status"))
      (with-current-buffer origin (font-lock-flush)))))

(defun coil-live-eval-region (beg end)
  "Compile and atomically publish the selected Coil forms."
  (interactive "r")
  (nrepl-send-request
   (list "op" "eval" "code" (buffer-substring-no-properties beg end))
   (coil-live--handler (current-buffer))
   (coil-live--connection)))

(defun coil-live-eval-defun ()
  "Compile and publish the top-level form at point."
  (interactive)
  (save-excursion
    (end-of-defun)
    (let ((end (point)))
      (beginning-of-defun)
      (coil-live-eval-region (point) end))))

(defun coil-live-load-buffer ()
  "Submit the buffer as one live edit transaction."
  (interactive)
  (nrepl-send-request
   (list "op" "load-file"
         "file" (buffer-substring-no-properties (point-min) (point-max))
         "file-path" (or buffer-file-name "<buffer>"))
   (coil-live--handler (current-buffer))
   (coil-live--connection)))

(defun coil-live-state ()
  "Show the live runtime's exact transactional state as JSON."
  (interactive)
  (nrepl-send-request
   (list "op" "coil/state")
   (lambda (response)
     (when-let ((value (nrepl-dict-get response "value")))
       (with-current-buffer (get-buffer-create "*coil-live-state*")
         (let ((inhibit-read-only t))
           (erase-buffer)
           (insert value)
           (json-pretty-print-buffer)
           (json-ts-mode)
           (display-buffer (current-buffer))))))
   (coil-live--connection)))

;; No keys are bound here on purpose.  Every C-c prefix coil-live would want
;; is already taken by `coil-mode' (C-c C-c eval, C-c C-r run, C-c C-k load,
;; C-c C-z REPL), and binding into `coil-mode-map' would shadow them for every
;; Coil buffer.  Reach these four through M-x:
;;
;;   coil-live-eval-defun   coil-live-eval-region
;;   coil-live-load-buffer  coil-live-state

(provide 'coil-live)
;;; coil-live.el ends here
