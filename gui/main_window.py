import re

from PyQt6.QtCore import Qt, QStringListModel, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controllers.recherche_controller import RechercheController
from gui.results_table import EntrepriseFilterProxyModel, EntrepriseTableModel
from utils.constants import LISTE_NAF_SELECTION, TRANCHES_EFFECTIFS


class EntrepriseSearchApp(QWidget):
    def __init__(self):
        super().__init__()

        self.controller = RechercheController()
        self.communes_trouvees = []
        self.communes_checkboxes = {}
        self.resultats_complets = []

        self.table_model = EntrepriseTableModel()
        self.proxy_model = EntrepriseFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.timer_autocompletion = QTimer(self)
        self.timer_autocompletion.setSingleShot(True)
        self.timer_autocompletion.timeout.connect(self.executer_appel_api_commune)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Prospector V2 - Refactoring V1")
        self.resize(1000, 900)

        main_layout = QVBoxLayout(self)

        geo_group = QGroupBox("Zone géographique")
        geo_layout = QVBoxLayout(geo_group)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Commune centre :"))

        self.input_commune = QLineEdit()
        self.input_commune.setPlaceholderText("Saisissez le nom d'une commune...")
        self.input_commune.textChanged.connect(self.declencher_timer_autocompletion)

        self.completer_model = QStringListModel(self)
        self.completer = QCompleter(self)
        self.completer.setModel(self.completer_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.input_commune.setCompleter(self.completer)

        input_layout.addWidget(self.input_commune)
        input_layout.addWidget(QLabel("Rayon :"))

        self.combo_rayon = QComboBox()
        self.combo_rayon.addItems([
            "0 km (Uniquement la ville)",
            "5 km",
            "10 km",
            "20 km",
            "30 km",
        ])
        self.combo_rayon.setCurrentIndex(2)
        input_layout.addWidget(self.combo_rayon)

        self.btn_calculer_zone = QPushButton("1. Calculer la zone")
        self.btn_calculer_zone.setStyleSheet(
            "background-color: #17a2b8; color: white; font-weight: bold;"
        )
        self.btn_calculer_zone.clicked.connect(self.calculer_communes_rayon)
        input_layout.addWidget(self.btn_calculer_zone)

        geo_layout.addLayout(input_layout)
        geo_layout.addWidget(QLabel("Communes incluses (décochez pour exclure) :"))

        self.scroll_communes = QScrollArea()
        self.scroll_communes.setWidgetResizable(True)
        self.scroll_communes.setFixedHeight(120)

        self.widget_communes_content = QWidget()
        self.layout_communes_list = QVBoxLayout(self.widget_communes_content)
        self.layout_communes_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_communes.setWidget(self.widget_communes_content)

        geo_layout.addWidget(self.scroll_communes)
        main_layout.addWidget(geo_group)

        main_layout.addWidget(QLabel("<b>Filtres d'activité et d'effectifs :</b>"))

        act_layout = QHBoxLayout()
        act_layout.addWidget(QLabel("Secteur / activité principale :"))

        self.combo_act = QComboBox()
        for code, libelle in LISTE_NAF_SELECTION.items():
            texte_affichage = libelle if code == "TOUS" else f"{code} - {libelle}"
            self.combo_act.addItem(texte_affichage, code)
        act_layout.addWidget(self.combo_act)
        main_layout.addLayout(act_layout)

        eff_layout = QHBoxLayout()
        eff_layout.addWidget(QLabel("Effectif maximum souhaité :"))
        self.combo_eff = QComboBox()
        for code, info in TRANCHES_EFFECTIFS.items():
            self.combo_eff.addItem(info[1], code)
        eff_layout.addWidget(self.combo_eff)
        main_layout.addLayout(eff_layout)

        buttons_layout = QHBoxLayout()

        self.btn_search = QPushButton("2. Lancer la recherche d'entreprises")
        self.btn_search.setStyleSheet(
            "font-weight: bold; padding: 10px; background-color: #0056b3; color: white;"
        )
        self.btn_search.setEnabled(False)
        self.btn_search.clicked.connect(self.performer_recherche)
        buttons_layout.addWidget(self.btn_search)

        self.btn_csv = QPushButton("Exporter en CSV")
        self.btn_csv.setStyleSheet(
            "font-weight: bold; padding: 10px; background-color: #28a745; color: white;"
        )
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(self.exporter_csv)
        buttons_layout.addWidget(self.btn_csv)
        main_layout.addLayout(buttons_layout)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtrer les résultats :"))
        self.input_filtre = QLineEdit()
        self.input_filtre.setPlaceholderText(
            "Nom, SIREN, activité, commune, dirigeant..."
        )
        self.input_filtre.textChanged.connect(self.filtrer_resultats)
        filter_layout.addWidget(self.input_filtre)
        main_layout.addLayout(filter_layout)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(260)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        main_layout.addWidget(self.table)

        stats_layout = QHBoxLayout()
        self.lbl_nb = QLabel("Entreprises : 0")
        self.lbl_siret = QLabel("SIRET : 0")
        self.lbl_dirigeants = QLabel("Dirigeants : 0")

        for label in (self.lbl_nb, self.lbl_siret, self.lbl_dirigeants):
            label.setObjectName("statsLabel")
            label.setStyleSheet(
                "background-color: #EAF4FF; color: #000000; "
                "border: 1px solid #7AA7D9; border-radius: 6px; "
                "padding: 8px; font-weight: bold;"
            )
            stats_layout.addWidget(label)

        stats_layout.addStretch()
        main_layout.addLayout(stats_layout)

        main_layout.addWidget(QLabel("<b>Journal :</b>"))
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setMinimumHeight(160)
        main_layout.addWidget(self.result_area)

        self.status_label = QLabel("Prêt")
        self.status_label.setStyleSheet(
            "color: #000000; background-color: #F1F3F5; padding: 5px;"
        )
        main_layout.addWidget(self.status_label)

    def declencher_timer_autocompletion(self, texte):
        if len(texte.strip()) < 2:
            self.completer_model.setStringList([])
            return
        self.timer_autocompletion.start(300)

    def executer_appel_api_commune(self):
        texte = self.input_commune.text().strip()
        try:
            suggestions = self.controller.suggestions_communes(texte)
            self.completer_model.setStringList(suggestions)
        except Exception:
            self.completer_model.setStringList([])

    def calculer_communes_rayon(self):
        saisie = self.input_commune.text().strip()
        choix_rayon = self.combo_rayon.currentText()

        if not saisie:
            QMessageBox.warning(self, "Attention", "Veuillez saisir un nom de commune.")
            return

        self._vider_liste_communes()
        self.communes_trouvees = []
        self.btn_search.setEnabled(False)
        self.status_label.setText("Calcul de la zone en cours...")

        try:
            self.communes_trouvees = self.controller.calculer_communes_rayon(
                saisie=saisie,
                choix_rayon=choix_rayon,
            )
            self._afficher_communes()
            self.btn_search.setEnabled(True)
            self.status_label.setText(
                f"Zone calculée : {len(self.communes_trouvees)} commune(s)"
            )
            QMessageBox.information(
                self,
                "Zone calculée",
                f"{len(self.communes_trouvees)} commune(s) trouvée(s) dans le secteur.",
            )
        except Exception as exc:
            self.status_label.setText("Erreur lors du calcul de la zone")
            QMessageBox.critical(
                self,
                "Erreur technique",
                f"Erreur lors du traitement : {exc}",
            )

    def _vider_liste_communes(self):
        for index in reversed(range(self.layout_communes_list.count())):
            item = self.layout_communes_list.itemAt(index)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def _afficher_communes(self):
        self.widget_communes_content = QWidget()
        self.layout_communes_list = QVBoxLayout(self.widget_communes_content)
        self.layout_communes_list.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.communes_checkboxes = {}
        for commune in self.communes_trouvees:
            checkbox = QCheckBox(commune.label())
            checkbox.setChecked(True)
            self.communes_checkboxes[commune.code] = checkbox
            self.layout_communes_list.addWidget(checkbox)

        self.scroll_communes.setWidget(self.widget_communes_content)

    def performer_recherche(self):
        communes_valides = [
            commune
            for commune in self.communes_trouvees
            if self.communes_checkboxes.get(commune.code)
            and self.communes_checkboxes[commune.code].isChecked()
        ]

        if not communes_valides:
            QMessageBox.warning(
                self,
                "Attention",
                "Veuillez cocher au moins une commune.",
            )
            return

        self.result_area.setText(
            f"Lancement de la recherche sur {len(communes_valides)} commune(s)..."
        )
        self.status_label.setText("Recherche en cours...")
        self.btn_search.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.input_filtre.clear()

        try:
            resultats = self.controller.rechercher_entreprises(
                communes=communes_valides,
                code_naf_selectionne=self.combo_act.currentData(),
                code_tranche_max=self.combo_eff.currentData(),
                message_callback=self._message_recherche,
            )

            self.resultats_complets = resultats
            self.table_model.set_entreprises(resultats)
            self.proxy_model.invalidateFilter()
            self.table.resizeColumnsToContents()
            self._mettre_a_jour_stats(resultats)

            if not resultats:
                self.result_area.setText("Aucun résultat trouvé avec vos critères.")
                self.status_label.setText("Recherche terminée : aucun résultat")
            else:
                self.btn_csv.setEnabled(True)
                self.result_area.append(
                    f"Extraction terminée : {len(resultats)} entreprise(s) collectée(s)."
                )
                self.status_label.setText(
                    f"Recherche terminée : {len(resultats)} entreprise(s)"
                )

        except Exception as exc:
            self.result_area.setText(f"Erreur réseau : {exc}")
            self.status_label.setText("Erreur pendant la recherche")
        finally:
            self.btn_search.setEnabled(True)

    def filtrer_resultats(self, texte):
        self.proxy_model.setFilterFixedString(texte)
        self._mettre_a_jour_stats_filtrees(self.proxy_model.rowCount())

    def _mettre_a_jour_stats_filtrees(self, nb_affiches):
        nb_total = len(self.resultats_complets)
        if nb_affiches == nb_total:
            self.lbl_nb.setText(f"Entreprises : {nb_total}")
        else:
            self.lbl_nb.setText(
                f"Entreprises : {nb_affiches} affichée(s) / {nb_total}"
            )

    def _mettre_a_jour_stats(self, resultats):
        nb = len(resultats)
        nb_siret = sum(1 for entreprise in resultats if entreprise.siret)
        nb_dirigeants = sum(
            1 for entreprise in resultats if entreprise.dirigeant.nom
        )
        self.lbl_nb.setText(f"Entreprises : {nb}")
        self.lbl_siret.setText(f"SIRET : {nb_siret}")
        self.lbl_dirigeants.setText(f"Dirigeants : {nb_dirigeants}")

    def _message_recherche(self, message):
        self.result_area.append(message)
        QApplication.processEvents()

    def exporter_csv(self):
        if not self.controller.resultats:
            return

        saisie_commune = self.input_commune.text().strip()
        nom_commune = (
            saisie_commune.split(" (")[0]
            if " (" in saisie_commune
            else saisie_commune
        )
        rayon_str = self.combo_rayon.currentText().split(" ")[0] + "_Km"
        code_act = self.combo_act.currentData()
        nom_activite = LISTE_NAF_SELECTION.get(code_act, "Toutes_Activites")

        nom_propose = f"Entreprises-{nom_commune}_{rayon_str}_{nom_activite}"
        nom_propose = re.sub(r'[\\/*?:"<>|]', "", nom_propose).replace(" ", "_")

        fichier, _ = QFileDialog.getSaveFileName(
            self,
            "Sauvegarder CSV",
            f"{nom_propose}.csv",
            "CSV (*.csv)",
        )

        if not fichier:
            return

        try:
            self.controller.exporter_csv(fichier)
            QMessageBox.information(
                self,
                "Succès",
                "Fichier CSV exporté avec succès.",
            )
            self.status_label.setText(f"Export CSV terminé : {fichier}")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
