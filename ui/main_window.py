import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPlainTextEdit, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSpinBox, QProgressBar, QFileDialog, QGroupBox, QTabWidget, QSplitter,
    QInputDialog,
)

from core import config
from core import profiles
from core import session_store
from core.pipeline import MoviePipeline

APP_NAME = "Flux Automation - FLUX 3 Movie Pipeline"


class PipelineWorker(QThread):
    stage = Signal(str)
    progress = Signal(int, int)
    message = Signal(str)
    finished_ok = Signal(dict)

    def __init__(self, prompts, settings, email, password, cookie_string=""):
        super().__init__()
        self.pipeline = None
        self.prompts = prompts
        self.settings = settings
        self.email = email
        self.password = password
        self.cookie_string = cookie_string

    def run(self):
        self.pipeline = MoviePipeline(
            self.prompts, self.settings, email=self.email, password=self.password,
            cookie_string=self.cookie_string,
            on_stage=lambda m: self.stage.emit(m),
            on_progress=lambda a, b: self.progress.emit(a, b),
            on_message=lambda m: self.message.emit(m),
            on_finished=lambda r: self.finished_ok.emit(r),
        )
        self.pipeline.run()

    def stop(self):
        if self.pipeline is not None:
            self.pipeline.request_stop()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1000, 720)
        self.settings = config.load_settings()
        self.worker = None
        self._build_ui()
        self._load_prompts_file()
        self._apply_settings()
        self._reload_profiles()
        saved_email, saved_password = session_store.load_credentials()
        if self.settings.get("email"):
            self.email_input.setText(self.settings["email"])
        elif saved_email:
            self.email_input.setText(saved_email)
        if saved_password:
            self.password_input.setText(saved_password)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Vertical)
        layout.addWidget(splitter, 1)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        prompts_group = QGroupBox("Scene prompts (one per line)")
        pg = QGridLayout(prompts_group)
        self.prompts_edit = QPlainTextEdit()
        self.prompt_count = QLabel("0 prompts")
        btn_load = QPushButton("Load file")
        btn_save = QPushButton("Save prompts.txt")
        btn_load.clicked.connect(self._load_prompts)
        btn_save.clicked.connect(self._save_prompts_file)
        pg.addWidget(self.prompts_edit, 0, 0, 1, 3)
        pg.addWidget(self.prompt_count, 1, 0)
        pg.addWidget(btn_load, 1, 1)
        pg.addWidget(btn_save, 1, 2)
        top_layout.addWidget(prompts_group, 1)

        right = QWidget()
        rl = QVBoxLayout(right)

        settings_group = QGroupBox("Settings")
        sg = QGridLayout(settings_group)
        sg.addWidget(QLabel("Ratio (target):"), 0, 0)
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(["16:9", "9:16"])
        sg.addWidget(self.ratio_combo, 0, 1)

        sg.addWidget(QLabel("Resolution:"), 1, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["hd", "fhd"])
        sg.addWidget(self.resolution_combo, 1, 1)

        sg.addWidget(QLabel("Continuation:"), 2, 0)
        self.continuation_combo = QComboBox()
        self.continuation_combo.addItems(["i2v", "v2v"])
        sg.addWidget(self.continuation_combo, 2, 1)

        sg.addWidget(QLabel("Retries per scene:"), 3, 0)
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(3)
        sg.addWidget(self.retries_spin, 3, 1)

        sg.addWidget(QLabel("Output folder:"), 4, 0)
        out_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        btn_out = QPushButton("...")
        btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(btn_out)
        sg.addLayout(out_row, 4, 1)

        self.keep_audio_check = QCheckBox("Keep clip audio (FLUX native sound)")
        sg.addWidget(self.keep_audio_check, 5, 0, 1, 2)
        self.music_bed_check = QCheckBox("Add quiet music bed over audio (needs assets/music)")
        sg.addWidget(self.music_bed_check, 6, 0, 1, 2)
        rl.addWidget(settings_group)

        creds_group = QGroupBox("Account (bfl.ai)")
        cg = QGridLayout(creds_group)
        cg.addWidget(QLabel("Email:"), 0, 0)
        self.email_input = QLineEdit()
        cg.addWidget(self.email_input, 0, 1)
        cg.addWidget(QLabel("Password:"), 1, 0)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        cg.addWidget(self.password_input, 1, 1)
        rl.addWidget(creds_group)

        profile_group = QGroupBox("Profiles (cookie string)")
        pgx = QGridLayout(profile_group)
        pgx.addWidget(QLabel("Profile:"), 0, 0)
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        pgx.addWidget(self.profile_combo, 0, 1)
        btn_paste = QPushButton("Paste new")
        btn_paste.clicked.connect(self._profile_paste)
        btn_delete = QPushButton("Delete")
        btn_delete.clicked.connect(self._profile_delete)
        pgx.addWidget(btn_paste, 0, 2)
        pgx.addWidget(btn_delete, 0, 3)
        self.cookie_edit = QPlainTextEdit()
        self.cookie_edit.setPlaceholderText("Paste a full cookie string here (name=value; name2=value2) for this profile")
        pgx.addWidget(self.cookie_edit, 1, 0, 1, 4)
        btn_save = QPushButton("Save cookie string")
        btn_save.clicked.connect(self._profile_save)
        pgx.addWidget(btn_save, 2, 0, 1, 4)
        rl.addWidget(profile_group)

        self.start_btn = QPushButton("Start pipeline")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.reset_btn = QPushButton("Reset progress")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.reset_btn.clicked.connect(self._reset)
        rl.addWidget(self.start_btn)
        rl.addWidget(self.stop_btn)
        rl.addWidget(self.reset_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        rl.addWidget(QLabel("Scene progress:"))
        rl.addWidget(self.progress)
        self.stage_label = QLabel("idle")
        rl.addWidget(self.stage_label)
        rl.addStretch(1)

        top_layout.addWidget(right, 1)
        splitter.addWidget(top)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        splitter.addWidget(self.log_edit)
        splitter.setSizes([460, 260])

    def _log(self, text):
        self.log_edit.appendPlainText(text)

    def _apply_settings(self):
        self.ratio_combo.setCurrentText(self.settings.get("ratio", "16:9"))
        self.resolution_combo.setCurrentText(self.settings.get("resolution", "hd"))
        self.continuation_combo.setCurrentText(self.settings.get("continuation", "i2v"))
        self.retries_spin.setValue(int(self.settings.get("retries", 3)))
        self.output_edit.setText(self.settings.get("output_dir", ""))
        self.keep_audio_check.setChecked(bool(self.settings.get("keep_audio", True)))
        self.music_bed_check.setChecked(bool(self.settings.get("music_bed", False)))

    def _collect_settings(self):
        self.settings["ratio"] = self.ratio_combo.currentText()
        self.settings["resolution"] = self.resolution_combo.currentText()
        self.settings["continuation"] = self.continuation_combo.currentText()
        self.settings["retries"] = self.retries_spin.value()
        self.settings["output_dir"] = self.output_edit.text().strip() or config.DEFAULT_SETTINGS["output_dir"]
        self.settings["keep_audio"] = self.keep_audio_check.isChecked()
        self.settings["music_bed"] = self.music_bed_check.isChecked()
        email = self.email_input.text().strip()
        self.settings["email"] = email
        password = self.password_input.text()
        if email and password:
            session_store.save_credentials(email, password)
        config.save_settings(self.settings)
        return self.settings

    def _prompts(self):
        lines = [ln.strip() for ln in self.prompts_edit.toPlainText().splitlines()]
        return [ln for ln in lines if ln]

    def _count_prompts(self):
        self.prompt_count.setText(f"{len(self._prompts())} prompts")

    def _load_prompts_file(self):
        path = Path(self.settings["prompts_file"])
        if path.exists():
            self.prompts_edit.setPlainText(path.read_text(encoding="utf-8"))
        self._count_prompts()

    def _save_prompts_file(self):
        path = Path(self.settings["prompts_file"])
        path.write_text("\n".join(self._prompts()), encoding="utf-8")
        self._log(f"Saved {len(self._prompts())} prompts to {path}")

    def _load_prompts(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open prompts", "", "Text files (*.txt);;All files (*)")
        if path:
            self.prompts_edit.setPlainText(Path(path).read_text(encoding="utf-8"))
            self._count_prompts()

    def _pick_output(self):
        path = QFileDialog.getExistingDirectory(self, "Output folder", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def _profile_changed(self, index):
        name = self.profile_combo.currentText()
        if not name:
            self.cookie_edit.setPlainText("")
            return
        data = profiles.get_profile(name)
        self.cookie_edit.setPlainText(data.get("cookie_string", "") if data else "")

    def _reload_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("")
        for name in profiles.load_profiles():
            self.profile_combo.addItem(name.get("name", ""))
        self.profile_combo.setCurrentIndex(0)
        self.profile_combo.blockSignals(False)
        self._profile_changed(0)

    def _selected_cookie(self):
        name = self.profile_combo.currentText()
        data = profiles.get_profile(name)
        if not data:
            return ""
        return data.get("cookie_string", "") or self.cookie_edit.toPlainText().strip()

    def _profile_paste(self):
        name, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        if not ok or not name.strip():
            return
        profiles.upsert_profile(name.strip(), "")
        self._reload_profiles()
        idx = self.profile_combo.findText(name.strip())
        self.profile_combo.setCurrentIndex(idx)

    def _profile_save(self):
        name = self.profile_combo.currentText()
        if not name:
            self._log("Select or create a profile first.")
            return
        cookies = self.cookie_edit.toPlainText().strip()
        if not cookies:
            self._log("Nothing to save.")
            return
        profiles.upsert_profile(name, cookies)
        self._log(f"Saved cookie string for profile '{name}'.")

    def _profile_delete(self):
        name = self.profile_combo.currentText()
        if not name:
            return
        profiles.delete_profile(name)
        self._reload_profiles()
        self._log(f"Deleted profile '{name}'.")

    def _start(self):
        if self.worker is not None and self.worker.isRunning():
            return
        prompts = self._prompts()
        if not prompts:
            self._log("Add at least one prompt.")
            return
        settings = self._collect_settings()
        self._save_prompts_file()
        self.progress.setRange(0, len(prompts))
        self.progress.setValue(0)
        self.stage_label.setText("starting")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        email = settings.get("email", "")
        password = self.password_input.text()
        cookie_string = self._selected_cookie()
        self.worker = PipelineWorker(prompts, settings, email, password, cookie_string)
        self.worker.stage.connect(self.stage_label.setText)
        self.worker.progress.connect(lambda a, b: self.progress.setValue(a))
        self.worker.message.connect(self._log)
        self.worker.finished_ok.connect(self._finished)
        self.worker.finished.connect(self._worker_done)
        self._log(f"Starting pipeline with {len(prompts)} scenes.")
        self.worker.start()

    def _stop(self):
        if self.worker is not None:
            self._log("Stop requested...")
            self.worker.stop()

    def _worker_done(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _finished(self, result):
        if result.get("ok"):
            self.stage_label.setText("complete")
            self._log(f"Done: {result.get('scenes_done')}/{result.get('total')} scenes -> {result.get('final')}")
        else:
            self.stage_label.setText("stopped/failed")
            self._log(f"Pipeline finished: {result.get('error')}")

    def _reset(self):
        path = Path(self.settings["state_file"])
        if path.exists():
            path.unlink()
            self._log("Progress reset.")
        else:
            self._log("No saved progress found.")

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()