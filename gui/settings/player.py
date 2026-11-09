import json
import re
import webbrowser

import customtkinter as ctk

import curio_collection_fetch
import toasts
from fonts import make_font
from logger import log_message
from settings import get_setting, set_setting
from gui.settings.common import _safe_combo_values


class PlayerSettingsMixin:
    # -------------------------------
    # Player & League
    # -------------------------------
    def _build_player(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="PoE Profile (player#1234):").grid(row=row, column=0, sticky="w")

        self.poe_entry = ctk.CTkEntry(frame, textvariable=self.poe_player_var, width=self.width)

        self.poe_entry.grid(row=row, column=1, sticky="w")

        self.poe_entry.configure(validate="key",
                                 validatecommand=(self.poe_entry.register(self._validate_poe_live), "%P"))

        self.poe_player_var.trace_add("write", self._update_tracker_poe_player)

        row += 1

        # --------------------------------
        # poe.ninja league
        # --------------------------------
        ctk.CTkLabel(frame, text="Pricing League:").grid(row=row, column=0, sticky="w", pady=(6, 0))

        league_cb = ctk.CTkComboBox(frame, variable=self.data_league_var, values=self.data_league_values,
                                    width=self.width, state="readonly")

        league_cb.grid(row=row, column=1, sticky="w", pady=(6, 0))

        self.data_league_var.trace_add("write", self._on_data_league_change)

        row += 1

        ctk.CTkLabel(frame, text="PoE Ladder Collection", font=make_font(12, "bold")
                     ).grid(row=row, column=0, sticky="w", pady=(5, 3))

        self.poeladder_label = ctk.CTkLabel(frame, text="How to setup", font=make_font(11, "bold", underline=True),
                                            cursor="hand2")
        self.poeladder_label.grid(row=row, column=1, sticky="w")

        self.poeladder_label.bind("<Button-1>", self.open_poeladder_link)

        row += 1

        already_fetched = (bool(
            self.poe_player_var.get().strip()) and self.poeladder_cached_profile == self.poe_player_var.get().strip() and bool(
            self.league_display_mapping))

        fetch_enabled = (self.enable_poeladder_var.get() and not already_fetched)

        self.fetch_collection_btn = ctk.CTkButton(frame, text=(
            "Collection Fetched" if already_fetched else "Fetch Collection"),
                                                  state=("normal" if fetch_enabled else "disabled"),
                                                  command=self._fetch_poeladder, width=self.long_width)

        self.fetch_collection_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))

        row += 1

        ctk.CTkCheckBox(frame, text="Enable PoELadder | Collection", variable=self.enable_poeladder_var,
                        command=self._toggle_poeladder).grid(row=row, column=0, sticky="w", pady=(8, 0))

        poeladder_values = _safe_combo_values(
            self.league_display_mapping.keys() if self.league_display_mapping else self.poeladder_leagues)

        if not poeladder_values:
            poeladder_values = [""]

        selected = self.dynamic_data_league_var.get().strip()

        if selected and selected not in poeladder_values:
            poeladder_values.insert(0, selected)

        self.dynamic_data_league_cb = ctk.CTkComboBox(frame, variable=self.dynamic_data_league_var,
                                                      values=poeladder_values, width=self.width, state=(
                "readonly" if self.enable_poeladder_var.get() else "disabled"))

        self.dynamic_data_league_cb.grid(row=row, column=1, sticky="w", pady=(8, 0))

        self.dynamic_data_league_var.trace_add("write", self._on_dynamic_league_change)

    # -------------------------------
    # Validation / Links
    # -------------------------------
    def _validate_poe_live(self, proposed_value):
        if re.match(r"^[A-Za-z0-9_#]*$", proposed_value):
            return True

        self.parent.bell()
        return False

    def open_poeladder_link(self, event=None):
        webbrowser.open(
            "https://poeladder.com/faqs#How_do_I_know_which_item_to_pick_from_a_Curio_box_when_I_run_a_Grand_Heist_Wing"
        )

    # -------------------------------
    # PoE Ladder
    # -------------------------------
    def _toggle_poeladder(self):
        enabled = self.enable_poeladder_var.get()

        set_setting("Application", "enable_poeladder", enabled)

        log_message("PoE Ladder", enabled)

        if self.dynamic_data_league_cb:
            self.dynamic_data_league_cb.configure(state=("readonly" if enabled else "disabled"))

        self._refresh_poeladder_fetch_state()

        self.tree_manager.refresh_treeview(self.tracker)

    def _fetch_poeladder(self):
        player = self.poe_player_var.get().strip()

        if not re.match(r"^[A-Za-z0-9_]+#[0-9]{4}$", player):
            toasts.show_message(
                self.parent,
                "Invalid PoE profile! Must be in format 'player#1234'."
            )

            if self.poe_entry:
                self.poe_entry.focus_set()

            return

        log_message(
            "PoE Ladder",
            f"Fetching collection for {player}"
        )

        if self.fetch_collection_btn:
            self.fetch_collection_btn.configure(state="disabled", text="Fetching...")

        curio_collection_fetch.PLAYER_LADDERS.pop(
            player,
            None
        )

        try:
            curio_collection_fetch.run_fetch_curios_threaded(player, force=True)
        except Exception as error:
            log_message(
                "PoE Ladder",
                f"Failed to start collection fetch: {error}"
            )

            if self.fetch_collection_btn:
                self.fetch_collection_btn.configure(state="normal", text="Fetch Collection")

            return

        self._wait_for_poeladder_fetch(player, attempt=0)

    def _wait_for_poeladder_fetch(self, player, attempt=0):
        current_player = self.poe_player_var.get().strip()

        if current_player != player:
            self._refresh_poeladder_fetch_state()
            return

        player_ladders = (
            curio_collection_fetch.PLAYER_LADDERS.get(
                player,
                {}
            )
        )

        if player_ladders:
            self._complete_poeladder_fetch(
                player,
                player_ladders
            )
            return

        # Around 30 seconds total.
        max_attempts = 120

        if attempt >= max_attempts:
            log_message(
                "PoE Ladder",
                f"Timed out waiting for collection fetch for {player}"
            )

            if self.fetch_collection_btn:
                self.fetch_collection_btn.configure(
                    state="normal",
                    text="Fetch Collection"
                )

            return

        self.parent.after(
            250,
            lambda: self._wait_for_poeladder_fetch(
                player,
                attempt + 1
            )
        )

    def _complete_poeladder_fetch(self, player, player_ladders):
        self.league_display_mapping = dict(player_ladders)

        leagues = list(self.league_display_mapping.keys())

        self.poeladder_cached_profile = player

        set_setting("Application", "poeladder_cached_profile", player)

        set_setting("Application", "poeladder_league_mapping", json.dumps(self.league_display_mapping))

        saved_name = str(get_setting("Application", "poeladder_collection_league", "") or "").strip()

        saved_identifier = str(get_setting("Application", "poeladder_league_identifier", "") or "").strip()

        selected_name = ""

        if saved_name in self.league_display_mapping:
            selected_name = saved_name

        elif saved_identifier:
            selected_name = next(
                (
                    name
                    for name, identifier
                    in self.league_display_mapping.items()
                    if identifier == saved_identifier
                ),
                ""
            )

        if not selected_name and leagues:
            selected_name = leagues[0]

        if self.dynamic_data_league_cb:
            self.dynamic_data_league_cb.configure(values=leagues)

        if selected_name:
            self.dynamic_data_league_var.set(selected_name)

            self._save_poeladder_league(selected_name)

        if self.fetch_collection_btn:
            self.fetch_collection_btn.configure(state="disabled", text="Collection Fetched")

        log_message(
            "PoE Ladder",
            (
                f"Collection fetched for {player}; "
                f"{len(leagues)} league(s)"
            )
        )

        self.tracker.on_league_change()

        self.tree_manager.refresh_treeview(self.tracker)

    def _threaded_on_league_change(self):
        self.parent.after(0, lambda: self.tracker.on_league_change())

    def _on_dynamic_league_change(self, *_):
        league_name = (self.dynamic_data_league_var.get().strip())

        if not league_name:
            return

        self._save_poeladder_league(league_name)

    def _save_poeladder_league(self, league_name):
        ladder_identifier = (self.league_display_mapping.get(league_name))

        # Try the in-memory fetch result too.
        if not ladder_identifier:
            player = self.poe_player_var.get().strip()

            player_ladders = (curio_collection_fetch.PLAYER_LADDERS.get(player, {}))

            ladder_identifier = (player_ladders.get(league_name))

            if player_ladders:
                self.league_display_mapping = dict(player_ladders)

        set_setting("Application", "poeladder_collection_league", league_name)
        set_setting("Application", "poeladder_ggg_league", league_name)

        if ladder_identifier:
            set_setting("Application", "poeladder_league_identifier", ladder_identifier)

            log_message(
                "PoE Ladder",
                (
                    f"Collection league set to "
                    f"{league_name} "
                    f"({ladder_identifier})"
                )
            )
        else:
            log_message(
                "PoE Ladder",
                (
                    f"Collection league name saved as "
                    f"{league_name}; no identifier available"
                )
            )

        self.tracker.on_league_change()

        self.tree_manager.refresh_treeview(self.tracker)

    # -------------------------------
    # Records / Player
    # -------------------------------
    def _on_data_league_change(self, *_):
        val = self.data_league_var.get().strip()

        if not val:
            return

        if val not in self.data_league_values:
            log_message(
                "Settings",
                f"Ignoring invalid data league selection: {val!r}"
            )
            return

        set_setting(
            "Application",
            "data_league",
            val
        )

        self.tracker.on_league_change()

        self.tree_manager.refresh_treeview(
            self.tracker
        )

    def _update_tracker_poe_player(self, *_):
        val = self.poe_player_var.get().strip()

        set_setting("User", "poe_user", val)

        self.tracker.poe_user = val

        try:
            self.tree_manager.total_frame.player_name.set(
                val
            )
        except Exception:
            pass

        self._refresh_poeladder_fetch_state()

    def _refresh_poeladder_fetch_state(self):
        if not self.fetch_collection_btn:
            return

        player = self.poe_player_var.get().strip()

        enabled = self.enable_poeladder_var.get()

        fetched_for_current_profile = (
                bool(player) and player == self.poeladder_cached_profile and bool(self.league_display_mapping))

        if not enabled:
            self.fetch_collection_btn.configure(state="disabled", text="Fetch Collection")
            return

        if fetched_for_current_profile:
            self.fetch_collection_btn.configure(state="disabled", text="Collection Fetched")
        else:
            self.fetch_collection_btn.configure(state="normal", text="Fetch Collection")
