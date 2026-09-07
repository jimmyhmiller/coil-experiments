;;; coil-live.el --- Native Coil live programming over nREPL -*- lexical-binding: t; -*-

;; This uses nREPL as transport, but deliberately does not pretend Coil is
;; Clojure. Coil-specific operations and diagnostics stay explicit.

(require 'cl-lib)
(require 'lisp-mode)
(require 'nrepl-client)

(defgroup coil-live nil "Live Coil development." :group 'languages)

(defcustom coil-live-port-file ".nrepl-port"
  "Project-relative port file written by coil-live-nrepl."
  :type 'string)

(defvar-local coil-live-connection nil)
(defvar coil-live-last-state nil)

(define-derived-mode coil-mode lisp-mode "Coil"
  "Major mode for Coil source."
  (setq-local comment-start ";")
  (setq-local comment-start-skip ";+ *"))

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
                   (read-number "Coil nREPL port: "))))
    (setq coil-live-connection
          (process-buffer
           (nrepl-start-client-process
            (or host "127.0.0.1") port nil
            (lambda (_endpoint)
              (generate-new-buffer " *coil-live-connection*")))))
    (message "Connected to Coil live runtime on %s:%d" (or host "127.0.0.1") port)))

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

(define-key coil-mode-map (kbd "C-c C-c") #'coil-live-eval-defun)
(define-key coil-mode-map (kbd "C-c C-r") #'coil-live-eval-region)
(define-key coil-mode-map (kbd "C-c C-k") #'coil-live-load-buffer)
(define-key coil-mode-map (kbd "C-c C-z") #'coil-live-state)

(add-to-list 'auto-mode-alist '("\\.coil\\'" . coil-mode))

(provide 'coil-live)
;;; coil-live.el ends here
