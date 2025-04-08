import sys
import os
import time
import threading
import tempfile
from pathlib import Path
from functools import partial

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QProgressBar, QComboBox, 
    QSpinBox, QColorDialog, QTabWidget, QTextEdit, QSlider,
    QCheckBox, QGroupBox, QRadioButton, QSplitter, QMessageBox,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QToolBar,
    QStatusBar, QFontComboBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QImage, QAction
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

import main as subtitling_backend

class SubtitleWorker(QThread):
    progress_update = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str)
    subtitles_extracted = pyqtSignal(list)
    
    def __init__(self, input_path, output_path, model_path, subtitle_settings):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.model_path = model_path
        self.subtitle_settings = subtitle_settings
        self.temp_files = []
        
    def run(self):
        try:
            self.progress_update.emit("Extracting audio...", 10)
            
            audio_path = subtitling_backend.extract_audio(self.input_path)
            self.temp_files.append(audio_path)
            
            if not audio_path:
                self.finished.emit(False, "Failed to extract audio")
                return
            
            self.progress_update.emit("Transcribing audio...", 30)
            
            subtitles = subtitling_backend.transcribe_audio(audio_path, self.model_path)
            
            if not subtitles:
                self.finished.emit(False, "No speech detected or transcription failed")
                return
            
            self._apply_subtitle_settings(subtitles)
            
            self.subtitles_extracted.emit(subtitles)
            
            self.progress_update.emit("Cleaning up...", 95)
            self._cleanup()
            self.finished.emit(True, "Subtitling completed successfully")
            
        except Exception as e:
            self._cleanup()
            self.finished.emit(False, f"An error occurred: {str(e)}")
    
    def _apply_subtitle_settings(self, subtitles):
        pass
    
    def _cleanup(self):
        for file_path in self.temp_files:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

class VideoGenerationWorker(QThread):
    progress_update = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str, str)
    
    def __init__(self, input_path, output_path, subtitles, style_settings):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.subtitles = subtitles
        self.style_settings = style_settings
        
    def run(self):
        try:
            self.progress_update.emit("Adding subtitles to video...", 30)
            
            output_video = subtitling_backend.create_subtitled_video(
                self.input_path, self.subtitles, self.output_path)
            
            if not output_video:
                self.finished.emit(False, "Failed to create output video", "")
                return
            
            self.progress_update.emit("Video generation complete", 100)
            self.finished.emit(True, "Video created successfully", self.output_path)
            
        except Exception as e:
            self.finished.emit(False, f"An error occurred: {str(e)}", "")

class SubtitleEditor(QWidget):
    subtitle_updated = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.subtitles = []
        self.current_index = -1
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.subtitle_list = QListWidget()
        self.subtitle_list.currentRowChanged.connect(self.select_subtitle)
        layout.addWidget(QLabel("Subtitles:"))
        layout.addWidget(self.subtitle_list)
        
        editor_group = QGroupBox("Edit Subtitle")
        editor_layout = QVBoxLayout()
        
        self.text_edit = QTextEdit()
        editor_layout.addWidget(QLabel("Text:"))
        editor_layout.addWidget(self.text_edit)
        
        timing_layout = QHBoxLayout()
        self.start_time = QDoubleSpinBox()
        self.start_time.setDecimals(2)
        self.start_time.setSuffix(" sec")
        self.start_time.setRange(0, 99999)
        
        self.end_time = QDoubleSpinBox()
        self.end_time.setDecimals(2)
        self.end_time.setSuffix(" sec")
        self.end_time.setRange(0, 99999)
        
        timing_layout.addWidget(QLabel("Start:"))
        timing_layout.addWidget(self.start_time)
        timing_layout.addWidget(QLabel("End:"))
        timing_layout.addWidget(self.end_time)
        
        editor_layout.addLayout(timing_layout)
        
        button_layout = QHBoxLayout()
        
        self.update_btn = QPushButton("Update Subtitle")
        self.update_btn.clicked.connect(self.update_subtitle)
        button_layout.addWidget(self.update_btn)
        
        self.delete_btn = QPushButton("Delete Subtitle")
        self.delete_btn.clicked.connect(self.delete_subtitle)
        button_layout.addWidget(self.delete_btn)
        
        editor_layout.addLayout(button_layout)
        
        new_subtitle_layout = QHBoxLayout()
        self.new_subtitle_btn = QPushButton("Add New Subtitle")
        self.new_subtitle_btn.clicked.connect(self.add_new_subtitle)
        new_subtitle_layout.addWidget(self.new_subtitle_btn)
        editor_layout.addLayout(new_subtitle_layout)
        
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)
        
        self.setLayout(layout)
        
        self.update_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
    
    def load_subtitles(self, subtitles):
        self.subtitles = subtitles.copy() if subtitles else []
        self.refresh_subtitle_list()
        if self.subtitles:
            self.subtitle_list.setCurrentRow(0)
            self.update_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
    
    def refresh_subtitle_list(self):
        current_row = self.subtitle_list.currentRow()
        self.subtitle_list.clear()
        for subtitle in self.subtitles:
            start = subtitle["start_time"]
            end = subtitle["end_time"]
            text = subtitle["text"]
            text_preview = text[:40] + ("..." if len(text) > 40 else "")
            display_text = f"{self._format_time(start)} - {self._format_time(end)}: {text_preview}"
            self.subtitle_list.addItem(display_text)
        
        if current_row >= 0 and current_row < self.subtitle_list.count():
            self.subtitle_list.setCurrentRow(current_row)
        elif self.subtitle_list.count() > 0:
            self.subtitle_list.setCurrentRow(0)
    
    def select_subtitle(self, index):
        self.update_btn.setEnabled(index >= 0)
        self.delete_btn.setEnabled(index >= 0)
        
        if index < 0 or index >= len(self.subtitles):
            self.current_index = -1
            self.text_edit.clear()
            self.start_time.setValue(0)
            self.end_time.setValue(0)
            return
        
        self.current_index = index
        subtitle = self.subtitles[index]
        
        self.text_edit.blockSignals(True)
        self.start_time.blockSignals(True)
        self.end_time.blockSignals(True)
        
        self.text_edit.setText(subtitle["text"])
        self.start_time.setValue(subtitle["start_time"])
        self.end_time.setValue(subtitle["end_time"])
        
        self.text_edit.blockSignals(False)
        self.start_time.blockSignals(False)
        self.end_time.blockSignals(False)
    
    def update_subtitle(self):
        if self.current_index < 0 or self.current_index >= len(self.subtitles):
            return
        
        new_text = self.text_edit.toPlainText()
        new_start = self.start_time.value()
        new_end = self.end_time.value()
        
        if new_start >= new_end:
            QMessageBox.warning(self, "Invalid Time Range", 
                                "Start time must be less than end time.")
            return
        
        self.subtitles[self.current_index]["text"] = new_text
        self.subtitles[self.current_index]["start_time"] = new_start
        self.subtitles[self.current_index]["end_time"] = new_end
        
        self.refresh_subtitle_list()
        self.subtitle_updated.emit()
    
    def delete_subtitle(self):
        if self.current_index < 0 or self.current_index >= len(self.subtitles):
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete this subtitle?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            del self.subtitles[self.current_index]
            self.refresh_subtitle_list()
            self.subtitle_updated.emit()
    
    def add_new_subtitle(self):
        last_time = 0
        if self.subtitles:
            last_time = self.subtitles[-1]["end_time"]
        
        new_subtitle = {
            "text": "New subtitle text",
            "start_time": last_time + 0.5,
            "end_time": last_time + 3.5,
            "words": []
        }
        
        self.subtitles.append(new_subtitle)
        self.refresh_subtitle_list()
        self.subtitle_list.setCurrentRow(len(self.subtitles) - 1)
        self.subtitle_updated.emit()
    
    def get_subtitles(self):
        return self.subtitles.copy()
    
    def _format_time(self, seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 100)
        return f"{mins:02d}:{secs:02d}.{ms:02d}"

class StyleSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        font_group = QGroupBox("Font Settings")
        font_layout = QVBoxLayout()
        
        font_row = QHBoxLayout()
        self.font_combo = QFontComboBox()
        font_row.addWidget(QLabel("Font:"))
        font_row.addWidget(self.font_combo)
        font_layout.addLayout(font_row)
        
        size_row = QHBoxLayout()
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 72)
        self.font_size.setValue(28)
        size_row.addWidget(QLabel("Size:"))
        size_row.addWidget(self.font_size)
        font_layout.addLayout(size_row)
        
        style_row = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.italic_check = QCheckBox("Italic")
        style_row.addWidget(self.bold_check)
        style_row.addWidget(self.italic_check)
        font_layout.addLayout(style_row)
        
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)
        
        color_group = QGroupBox("Color Settings")
        color_layout = QVBoxLayout()
        
        text_color_row = QHBoxLayout()
        self.text_color_btn = QPushButton("  ")
        self.text_color_btn.setStyleSheet("background-color: white;")
        self.text_color = QColor(255, 255, 255)
        self.text_color_btn.clicked.connect(self.choose_text_color)
        text_color_row.addWidget(QLabel("Text Color:"))
        text_color_row.addWidget(self.text_color_btn)
        color_layout.addLayout(text_color_row)
        
        outline_color_row = QHBoxLayout()
        self.outline_color_btn = QPushButton("  ")
        self.outline_color_btn.setStyleSheet("background-color: black;")
        self.outline_color = QColor(0, 0, 0)
        self.outline_color_btn.clicked.connect(self.choose_outline_color)
        outline_color_row.addWidget(QLabel("Outline Color:"))
        outline_color_row.addWidget(self.outline_color_btn)
        color_layout.addLayout(outline_color_row)
        
        bg_color_row = QHBoxLayout()
        self.bg_color_btn = QPushButton("  ")
        self.bg_color_btn.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.bg_color = QColor(0, 0, 0, 150)
        self.bg_color_btn.clicked.connect(self.choose_bg_color)
        bg_color_row.addWidget(QLabel("Background:"))
        bg_color_row.addWidget(self.bg_color_btn)
        color_layout.addLayout(bg_color_row)
        
        opacity_row = QHBoxLayout()
        self.bg_opacity = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity.setRange(0, 100)
        self.bg_opacity.setValue(60)
        opacity_row.addWidget(QLabel("Opacity:"))
        opacity_row.addWidget(self.bg_opacity)
        color_layout.addLayout(opacity_row)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        position_group = QGroupBox("Position")
        position_layout = QVBoxLayout()
        
        self.position_bottom = QRadioButton("Bottom")
        self.position_top = QRadioButton("Top")
        self.position_bottom.setChecked(True)
        
        position_layout.addWidget(self.position_bottom)
        position_layout.addWidget(self.position_top)
        
        position_group.setLayout(position_layout)
        layout.addWidget(position_group)
        
        layout.addStretch()
        
        self.setLayout(layout)
    
    def choose_text_color(self):
        color = QColorDialog.getColor(self.text_color, self, "Choose Text Color")
        if color.isValid():
            self.text_color = color
            self.text_color_btn.setStyleSheet(f"background-color: {color.name()};")
    
    def choose_outline_color(self):
        color = QColorDialog.getColor(self.outline_color, self, "Choose Outline Color")
        if color.isValid():
            self.outline_color = color
            self.outline_color_btn.setStyleSheet(f"background-color: {color.name()};")
    
    def choose_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self, "Choose Background Color", options=QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.bg_color = color
            self.bg_color_btn.setStyleSheet(f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});")
    
    def get_settings(self):
        return {
            "font_family": self.font_combo.currentFont().family(),
            "font_size": self.font_size.value(),
            "bold": self.bold_check.isChecked(),
            "italic": self.italic_check.isChecked(),
            "text_color": self.text_color.getRgb(),
            "outline_color": self.outline_color.getRgb(),
            "bg_color": self.bg_color.getRgb(),
            "bg_opacity": self.bg_opacity.value() / 100.0,
            "position": "bottom" if self.position_bottom.isChecked() else "top"
        }

class VideoPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)
        
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        controls_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_btn)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.position_slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        controls_layout.addWidget(self.time_label)
        
        layout.addLayout(controls_layout)
        
        self.setLayout(layout)
        
        self.media_player.playbackStateChanged.connect(self.media_state_changed)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        
        self.play_btn.setEnabled(False)
    
    def load_video(self, file_path):
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.play_btn.setEnabled(True)
    
    def toggle_play(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
    
    def media_state_changed(self, state):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("Pause")
        else:
            self.play_btn.setText("Play")
    
    def position_changed(self, position):
        self.position_slider.setValue(position)
        self._update_time_label(position, self.media_player.duration())
    
    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)
        self._update_time_label(self.media_player.position(), duration)
    
    def set_position(self, position):
        self.media_player.setPosition(position)
    
    def _update_time_label(self, position, duration):
        position_str = self._format_time(position)
        duration_str = self._format_time(duration)
        self.time_label.setText(f"{position_str} / {duration_str}")
    
    def _format_time(self, ms):
        if ms <= 0:
            return "00:00"
        s = ms // 1000
        m = s // 60
        s %= 60
        return f"{m:02d}:{s:02d}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.input_video_path = ""
        self.output_video_path = ""
        self.model_path = ""
        self.subtitles = []
        
        self.init_ui()
        self.setWindowTitle("Video Subtitler")
        self.resize(1200, 800)
    
    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout()
        
        input_layout = QHBoxLayout()
        self.input_path_label = QLabel("No video selected")
        input_select_btn = QPushButton("Select Input Video")
        input_select_btn.clicked.connect(self.select_input_video)
        input_layout.addWidget(QLabel("Input Video:"))
        input_layout.addWidget(self.input_path_label, 1)
        input_layout.addWidget(input_select_btn)
        file_layout.addLayout(input_layout)
        
        output_layout = QHBoxLayout()
        self.output_path_label = QLabel("No output location selected")
        output_select_btn = QPushButton("Select Output Location")
        output_select_btn.clicked.connect(self.select_output_location)
        output_layout.addWidget(QLabel("Output Video:"))
        output_layout.addWidget(self.output_path_label, 1)
        output_layout.addWidget(output_select_btn)
        file_layout.addLayout(output_layout)
        
        model_layout = QHBoxLayout()
        self.model_path_label = QLabel("Using default model")
        model_select_btn = QPushButton("Select Custom Model")
        model_select_btn.clicked.connect(self.select_model)
        model_layout.addWidget(QLabel("Vosk Model:"))
        model_layout.addWidget(self.model_path_label, 1)
        model_layout.addWidget(model_select_btn)
        file_layout.addLayout(model_layout)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        self.tabs = QTabWidget()
        
        self.video_player = VideoPlayer()
        self.tabs.addTab(self.video_player, "Video Preview")
        
        self.subtitle_editor = SubtitleEditor()
        self.subtitle_editor.subtitle_updated.connect(self.on_subtitle_updated)
        self.tabs.addTab(self.subtitle_editor, "Subtitle Editor")
        
        self.style_settings = StyleSettings()
        self.tabs.addTab(self.style_settings, "Subtitle Style")
        
        main_layout.addWidget(self.tabs, 1)
        
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        button_layout = QHBoxLayout()
        
        self.extract_subtitles_btn = QPushButton("Extract Subtitles")
        self.extract_subtitles_btn.clicked.connect(self.extract_subtitles)
        button_layout.addWidget(self.extract_subtitles_btn)
        
        self.generate_video_btn = QPushButton("Generate Subtitled Video")
        self.generate_video_btn.clicked.connect(self.generate_video)
        self.generate_video_btn.setEnabled(False)
        button_layout.addWidget(self.generate_video_btn)
        
        self.export_srt_btn = QPushButton("Export SRT")
        self.export_srt_btn.clicked.connect(self.export_srt)
        self.export_srt_btn.setEnabled(False)
        button_layout.addWidget(self.export_srt_btn)
        
        main_layout.addLayout(button_layout)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.create_menu_bar()
    
    def create_menu_bar(self):
        menu_bar = self.menuBar()
        
        file_menu = menu_bar.addMenu("File")
        
        open_action = QAction("Open Video", self)
        open_action.triggered.connect(self.select_input_video)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Video As", self)
        save_action.triggered.connect(self.select_output_location)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        subtitle_menu = menu_bar.addMenu("Subtitles")
        
        extract_action = QAction("Extract from Video", self)
        extract_action.triggered.connect(self.extract_subtitles)
        subtitle_menu.addAction(extract_action)
        
        export_srt_action = QAction("Export SRT", self)
        export_srt_action.triggered.connect(self.export_srt)
        subtitle_menu.addAction(export_srt_action)
        
        help_menu = menu_bar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def select_input_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        
        if file_path:
            self.input_video_path = file_path
            self.input_path_label.setText(os.path.basename(file_path))
            
            base_name = os.path.splitext(file_path)[0]
            self.output_video_path = f"{base_name}_subtitled.mp4"
            self.output_path_label.setText(os.path.basename(self.output_video_path))
            
            self.video_player.load_video(file_path)
            
            self.status_bar.showMessage(f"Loaded: {os.path.basename(file_path)}")
    
    def select_output_location(self):
        if not self.input_video_path:
            QMessageBox.warning(self, "Warning", "Please select an input video first.")
            return
        
        suggested_name = os.path.splitext(os.path.basename(self.input_video_path))[0] + "_subtitled.mp4"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", suggested_name, "MP4 Video (*.mp4)")
        
        if file_path:
            self.output_video_path = file_path
            self.output_path_label.setText(os.path.basename(file_path))
    
    def select_model(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Vosk Model Directory")
        
        if dir_path:
            self.model_path = dir_path
            self.model_path_label.setText(os.path.basename(dir_path))
    
    def extract_subtitles(self):
        if not self.input_video_path:
            QMessageBox.warning(self, "Warning", "Please select an input video first.")
            return
        
        self.status_label.setText("Extracting subtitles...")
        self.progress_bar.setValue(10)
        
        self.extract_subtitles_btn.setEnabled(False)
        self.generate_video_btn.setEnabled(False)
        self.export_srt_btn.setEnabled(False)
        
        self.worker = SubtitleWorker(
            self.input_video_path, 
            self.output_video_path, 
            self.model_path, 
            self.style_settings.get_settings()
        )
        
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.extraction_finished)
        self.worker.subtitles_extracted.connect(self.set_subtitles)
        
        self.worker.start()
    
    def set_subtitles(self, subtitles):
        self.subtitles = subtitles
        self.subtitle_editor.load_subtitles(self.subtitles)
    
    def on_subtitle_updated(self):
        self.subtitles = self.subtitle_editor.get_subtitles()
    
    def update_progress(self, status, progress):
        self.status_label.setText(status)
        self.progress_bar.setValue(progress)
        self.status_bar.showMessage(status)
    
    def extraction_finished(self, success, message):
        if success:
            self.tabs.setCurrentWidget(self.subtitle_editor)
            
            self.generate_video_btn.setEnabled(True)
            self.export_srt_btn.setEnabled(True)
            
            QMessageBox.information(self, "Success", 
                f"Successfully extracted {len(self.subtitles)} subtitle segments.")
        else:
            QMessageBox.warning(self, "Error", message)
        
        self.extract_subtitles_btn.setEnabled(True)
        
        self.status_label.setText("Ready")
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Ready")
    
    def generate_video(self):
        if not self.subtitles:
            QMessageBox.warning(self, "Warning", "No subtitles available. Please extract subtitles first.")
            return
        
        if not self.output_video_path:
            QMessageBox.warning(self, "Warning", "Please select an output location.")
            return
        
        self.status_label.setText("Generating subtitled video...")
        self.progress_bar.setValue(10)
        
        self.extract_subtitles_btn.setEnabled(False)
        self.generate_video_btn.setEnabled(False)
        self.export_srt_btn.setEnabled(False)
        
        updated_subtitles = self.subtitle_editor.get_subtitles()
        
        self.video_worker = VideoGenerationWorker(
            self.input_video_path,
            self.output_video_path,
            updated_subtitles,
            self.style_settings.get_settings()
        )
        
        self.video_worker.progress_update.connect(self.update_progress)
        self.video_worker.finished.connect(self.generation_finished)
        
        self.video_worker.start()
    
    def generation_finished(self, success, message, output_path):
        if success:
            self.status_label.setText("Video generation complete")
            self.progress_bar.setValue(100)
            
            QTimer.singleShot(500, lambda: self.video_player.load_video(output_path))
            
            QMessageBox.information(self, "Success", 
                f"Subtitled video has been created at:\n{output_path}")
            
            self.tabs.setCurrentWidget(self.video_player)
        else:
            QMessageBox.warning(self, "Error", message)
        
        self.extract_subtitles_btn.setEnabled(True)
        self.generate_video_btn.setEnabled(True)
        self.export_srt_btn.setEnabled(True)
        
        self.status_label.setText("Ready")
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Ready")
    
    def export_srt(self):
        if not self.subtitles:
            QMessageBox.warning(self, "Warning", "No subtitles available. Please extract subtitles first.")
            return
        
        if self.input_video_path:
            suggested_name = os.path.splitext(os.path.basename(self.input_video_path))[0] + ".srt"
        else:
            suggested_name = "subtitles.srt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save SRT File", suggested_name, "SRT Files (*.srt)")
        
        if not file_path:
            return
        
        try:
            updated_subtitles = self.subtitle_editor.get_subtitles()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                for i, subtitle in enumerate(updated_subtitles, 1):
                    start_time = subtitle["start_time"]
                    end_time = subtitle["end_time"]
                    text = subtitle["text"]
                    
                    start_str = self._seconds_to_srt_time(start_time)
                    end_str = self._seconds_to_srt_time(end_time)
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{text}\n\n")
            
            QMessageBox.information(self, "Success", f"Subtitles exported to {file_path}")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to export SRT: {str(e)}")
    
    def _seconds_to_srt_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def show_about(self):
        QMessageBox.about(self, "About Video Subtitler",
            "Video Subtitler\n\n"
            "A tool for automatically generating subtitles for videos using speech recognition.\n\n"
            "Features:\n"
            "- Automatic speech recognition\n"
            "- Subtitle editing\n"
            "- Customizable subtitle styles\n"
            "- SRT export\n\n"
            "Powered by Vosk speech recognition."
        )

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()