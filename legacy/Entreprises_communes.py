import sys
import csv
import time
import requests
import re
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QScrollArea, QCheckBox, QTextEdit, 
    QFileDialog, QMessageBox, QComboBox, QGroupBox, QCompleter
)
from PyQt6.QtCore import Qt, QStringListModel, QTimer

# --- CODES NAF AVEC LIBELLÉS EN CLAIR ---
LISTE_NAF_SELECTION = {
    "TOUS": "Tous les secteurs / Toutes activités",
    "5610A": "Restauration traditionnelle",
    "5610B": "Cafétérias et autres libres-services",
    "5610C": "Restauration de type rapide (fast-food, sandwicheries, kebabs, food trucks, etc.)",
    "5621Z": "Services des traiteurs",
    "5629A": "Restauration collective sous contrat",
    "5629B": "Autres services de restauration n.c.a.",
    "5630Z": "Débits de boissons (bars, cafés, pubs, salons de thé avec licence)",
    "1071B": "Boulangerie et boulangerie-pâtisserie",
    "1071C": "Pâtisserie fraîche",
    "1013A": "Charcuterie",
    "4120A": "Construction de maisons individuelles",
    "4321A": "Électricien (Installation électrique)",
    "4322A": "Plombier / Chauffagiste",
    "4332A": "Menuiserie bois et PVC",
    "4334Z": "Peintre / Vitrier",
    "9602A": "Coiffure (Salons et à domicile)",
    "9602B": "Soins de beauté / Esthétique",
    "4711A": "Supérettes",
    "4711B": "Épiceries sociales ou de quartier",
    "4721Z": "Fruits et légumes (Primeur)",
    "4722Z": "Boucherie / Boucherie-Charcuterie",
    "4724Z": "Pain, pâtisserie et confiserie (Revente)",
    "4725Z": "Caviste / Boissons",
    "4761Z": "Librairie",
    "4762Z": "Journaux et papeterie",
    "4771Z": "Prêt-à-porter / Habillement",
    "4773Z": "Pharmacie de détail",
    "4776Z": "Fleuriste (Fleurs, plantes, graines)",
    "4777Z": "Bijouterie / Horlogerie",
    "7410Z": "Acivités spécialisées de design",
    "7111Z": "Activités d architecture"
}

TRANCHES_EFFECTIFS = {
    "TOUS": (-1, "Tous les effectifs"),
    "00": (0, "0 salarié (ou unité non employeuse)"),
    "01": (1, "1 ou 2 salariés"),
    "02": (3, "3 à 5 salariés"),
    "03": (6, "6 à 9 salariés"),
    "11": (10, "10 à 19 salariés"),
    "12": (20, "20 à 49 salariés"),
    "21": (50, "50 à 99 salariés")
}

# Ordre de priorité des qualités de dirigeant : un Gérant/Président/DG est le
# meilleur contact possible pour de la prospection (souvent celui qui décide),
# alors qu'un commissaire aux comptes ou un membre du conseil de surveillance
# est un mauvais contact commercial même s'il apparaît dans "dirigeants".
ORDRE_PRIORITE_QUALITES = [
    "gérant", "président", "directeur général", "directeur",
    "associé", "administrateur", "membre", "représentant",
]


def extraire_dirigeant_principal(ent):
    """Choisit, parmi le tableau 'dirigeants' renvoyé par
    recherche-entreprises.api.gouv.fr, la personne physique la plus
    pertinente pour de la prospection (en priorité un Gérant/Président/DG),
    en écartant les personnes morales (ex: cabinets d'expertise comptable)
    et les commissaires aux comptes. Retourne (prenom, nom, qualite) ou
    ("", "", "") si aucun dirigeant exploitable n'est trouvé."""
    dirigeants = ent.get("dirigeants") or []
    candidats = [d for d in dirigeants if d.get("type_dirigeant") == "personne physique"]
    if not candidats:
        return "", "", ""

    def rang_priorite(d):
        qualite = (d.get("qualite") or "").lower()
        if "commissaire" in qualite or "surveillance" in qualite:
            return len(ORDRE_PRIORITE_QUALITES) + 1  # rejeté en dernier recours seulement
        for i, mot_cle in enumerate(ORDRE_PRIORITE_QUALITES):
            if mot_cle in qualite:
                return i
        return len(ORDRE_PRIORITE_QUALITES)  # qualité inconnue : priorité moyenne

    candidats.sort(key=rang_priorite)
    meilleur = candidats[0]

    prenoms = (meilleur.get("prenoms") or "").strip()
    prenom = prenoms.split()[0].title() if prenoms else ""
    # Le nom peut contenir le nom de naissance entre parenthèses
    # (ex: "SAUTEUR (DURAND)") : on ne garde que le nom d'usage, avant la parenthèse.
    nom_brut = (meilleur.get("nom") or "").strip()
    nom = nom_brut.split("(")[0].strip().title()
    qualite = (meilleur.get("qualite") or "").strip()
    return prenom, nom, qualite


class EntrepriseSearchApp(QWidget):
    def __init__(self):
        super().__init__()
        self.derniers_resultats = []
        self.communes_trouvees = [] 
        
        # Minuteur pour l'anti-rebond (Debounce) de l'auto-complétion
        self.timer_autocompletion = QTimer()
        self.timer_autocompletion.setSingleShot(True)
        self.timer_autocompletion.timeout.connect(self.executer_appel_api_commune)
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Recherche Entreprises API - Optimisé & Export Sur-Mesure")
        self.resize(800, 850)
        
        main_layout = QVBoxLayout()
        
        # --- BLOC GÉOGRAPHIQUE ---
        geo_group = QGroupBox("Zone Géographique")
        geo_layout = QVBoxLayout()
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Commune centre :"))
        
        self.input_commune = QLineEdit()
        self.input_commune.setPlaceholderText("Tapez vite, la recherche attend que vous ayez fini...")
        self.input_commune.textChanged.connect(self.declencher_timer_autocompletion)
        
        self.completer_model = QStringListModel()
        self.completer = QCompleter()
        self.completer.setModel(self.completer_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.input_commune.setCompleter(self.completer)
        
        input_layout.addWidget(self.input_commune)
        
        input_layout.addWidget(QLabel("Rayon :"))
        self.combo_rayon = QComboBox()
        self.combo_rayon.addItems(["0 km (Uniquement la ville)", "5 km", "10 km", "20 km", "30 km"])
        self.combo_rayon.setCurrentIndex(2) 
        input_layout.addWidget(self.combo_rayon)
        
        self.btn_calculer_zone = QPushButton("1. Calculer la zone")
        self.btn_calculer_zone.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold;")
        self.btn_calculer_zone.clicked.connect(self.calculer_communes_rayon)
        input_layout.addWidget(self.btn_calculer_zone)
        geo_layout.addLayout(input_layout)
        
        geo_layout.addWidget(QLabel("Communes incluses (décochez pour exclure) :"))
        self.scroll_communes = QScrollArea()
        self.scroll_communes.setWidgetResizable(True)
        self.scroll_communes.setFixedHeight(120)
        self.widget_communes_content = QWidget()
        self.layout_communes_list = QVBoxLayout(self.widget_communes_content)
        self.scroll_communes.setWidget(self.widget_communes_content)
        geo_layout.addWidget(self.scroll_communes)
        
        geo_group.setLayout(geo_group.layout() or geo_layout)
        main_layout.addWidget(geo_group)
        
        # --- FILTRES PRINCIPAUX ---
        main_layout.addWidget(QLabel("<b>Filtres d'activité & effectifs :</b>"))
        
        act_layout = QHBoxLayout()
        act_layout.addWidget(QLabel("Secteur / Activité principale :"))
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
        
        # --- ACTIONS ---
        buttons_layout = QHBoxLayout()
        self.btn_search = QPushButton("2. Lancer la recherche d'entreprises")
        self.btn_search.setStyleSheet("font-weight: bold; padding: 10px; background-color: #0056b3; color: white;")
        self.btn_search.setEnabled(False)
        self.btn_search.clicked.connect(self.performer_recherche)
        buttons_layout.addWidget(self.btn_search)
        
        self.btn_csv = QPushButton("Exporter en CSV")
        self.btn_csv.setStyleSheet("font-weight: bold; padding: 10px; background-color: #28a745; color: white;")
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(self.exporter_csv)
        buttons_layout.addWidget(self.btn_csv)
        main_layout.addLayout(buttons_layout)
        
        # --- ZONE DE TEXTE ---
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        main_layout.addWidget(self.result_area)
        
        self.setLayout(main_layout)

    def declencher_timer_autocompletion(self, texte):
        """ Évite d'étouffer le réseau : relance le compte à rebours à chaque touche pressée """
        if len(texte.strip()) < 2:
            return
        # Attend 300ms d'inactivité de frappe avant de lancer la requête
        self.timer_autocompletion.start(300)

    def executer_appel_api_commune(self):
        """ Exécute l'appel API uniquement quand l'utilisateur a arrêté de taper """
        texte = self.input_commune.text().strip()
        if " (" in texte: # Évite de relancer l'API si l'utilisateur vient de valider un choix complet
            return
            
        try:
            url = "https://geo.api.gouv.fr/communes"
            res = requests.get(url, params={"nom": texte, "fields": "nom,codesPostaux", "limit": 10}, timeout=2)
            if res.status_code == 200:
                suggestions = []
                for item in res.json():
                    nom = item.get("nom", "")
                    cp = item.get("codesPostaux", [""])[0] if item.get("codesPostaux") else ""
                    suggestions.append(f"{nom} ({cp})")
                self.completer_model.setStringList(suggestions)
        except Exception:
            pass
    
    def calculer_communes_rayon(self):
        """ Utilise le calcul de distance local pour contourner le bug de l'API Géo """
        saisie = self.input_commune.text().strip()
        if not saisie:
            QMessageBox.warning(self, "Attention", "Veuillez saisir un nom de commune.")
            return
            
        if " (" in saisie:
            nom_saisi = saisie.split(" (")[0]
        else:
            nom_saisi = saisie
            
        # Nettoyage de l'affichage précédent
        for i in reversed(range(self.layout_communes_list.count())): 
            widget = self.layout_communes_list.itemAt(i).widget()
            if widget:
                widget.setParent(None)
            
        self.communes_trouvees = []
        self.btn_search.setEnabled(False)
        
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            # 1. On récupère la commune centre pour connaître son département et ses coordonnées de base
            url_base = "https://geo.api.gouv.fr/communes"
            res = requests.get(url_base, params={"nom": nom_saisi, "fields": "code,nom,centre,codesPostaux,codeDepartement", "exact": True}, headers=headers, timeout=5)
            
            if res.status_code != 200 or not res.json():
                res = requests.get(url_base, params={"nom": nom_saisi, "fields": "code,nom,centre,codesPostaux,codeDepartement"}, headers=headers, timeout=5)
                
            if res.status_code != 200 or not res.json():
                QMessageBox.critical(self, "Erreur", "Commune introuvable.")
                return
                
            commune_centre_data = res.json()[0]
            code_insee_centre = commune_centre_data["code"]
            nom_officiel_centre = commune_centre_data["nom"]
            code_dept = commune_centre_data.get("codeDepartement", "")
            
            if "centre" in commune_centre_data and "coordinates" in commune_centre_data["centre"]:
                lon, lat = commune_centre_data["centre"]["coordinates"]
            else:
                QMessageBox.critical(self, "Erreur", "Impossible de récupérer les coordonnées GPS du centre.")
                return
                
            cp_centre = commune_centre_data["codesPostaux"][0] if commune_centre_data.get("codesPostaux") else ""
            choix_rayon = self.combo_rayon.currentText()
            
            # Correction de la condition d'inclusion pour éviter le bug du "0 km" inclus dans "10 km"
            if choix_rayon.startswith("0 km"):
                self.communes_trouvees = [{"code": code_insee_centre, "nom": nom_officiel_centre, "cp": cp_centre}]
            else:
                rayon_km = int(choix_rayon.split(" ")[0])
                
                # SÉCURITÉ ABSOLUE : On télécharge toutes les communes du département (ex: 27 ou 76)
                # et on filtre nous-mêmes par le calcul mathématique.
                if code_dept:
                    url_dept = f"https://geo.api.gouv.fr/departements/{code_dept}/communes"
                    res_dept = requests.get(url_dept, params={"fields": "code,nom,codesPostaux,centre"}, headers=headers, timeout=5)
                    
                    if res_dept.status_code == 200:
                        import math
                        for c in res_dept.json():
                            if "centre" in c and "coordinates" in c["centre"]:
                                c_lon, c_lat = c["centre"]["coordinates"]
                                
                                # Formule mathématique de distance (approximation par Pythagore, largement suffisante pour < 50km)
                                # 111 km équivaut environ à 1 degré de latitude
                                dist_lat = (c_lat - lat) * 111
                                dist_lon = (c_lon - lon) * 111 * math.cos(math.radians(lat))
                                distance_approx = math.sqrt(dist_lat**2 + dist_lon**2)
                                
                                if distance_approx <= rayon_km:
                                    cp = c["codesPostaux"][0] if c.get("codesPostaux") else "N/A"
                                    self.communes_trouvees.append({"code": c["code"], "nom": c["nom"], "cp": cp})
            
            # Au cas où, on s'assure que la commune de départ est bien dans la liste
            if not any(c["code"] == code_insee_centre for c in self.communes_trouvees):
                self.communes_trouvees.append({"code": code_insee_centre, "nom": nom_officiel_centre, "cp": cp_centre})
                
            # Tri alphabétique des communes trouvées
            self.communes_trouvees = sorted(self.communes_trouvees, key=lambda x: x["nom"])
            
            # --- MISE À JOUR DE L'INTERFACE GRAPHIQUE ---
            if hasattr(self, 'widget_communes_content'):
                self.widget_communes_content.deleteLater()
                
            self.widget_communes_content = QWidget()
            self.layout_communes_list = QVBoxLayout(self.widget_communes_content)
            self.layout_communes_list.setAlignment(Qt.AlignmentFlag.AlignTop)
            
            self.communes_checkboxes = {}
            for c in self.communes_trouvees:
                cb = QCheckBox(f"{c['nom']} ({c['cp']})")
                cb.setChecked(True)
                self.communes_checkboxes[c["code"]] = cb
                self.layout_communes_list.addWidget(cb)
                
            self.scroll_communes.setWidget(self.widget_communes_content)
            self.widget_communes_content.adjustSize()
            
            self.btn_search.setEnabled(True)
            QMessageBox.information(self, "Zone calculée", f"{len(self.communes_trouvees)} commune(s) trouvée(s) dans le secteur.")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur technique", f"Erreur lors du traitement : {str(e)}")

 
    
    def performer_recherche(self):
        codes_insee_valides = [code for code, cb in self.communes_checkboxes.items() if cb.isChecked()]
        
        if not codes_insee_valides:
            QMessageBox.warning(self, "Attention", "Veuillez cocher au moins une commune.")
            return
            
        self.result_area.setText(f"Lancement de la recherche sur {len(codes_insee_valides)} commune(s)...")
        self.btn_search.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.derniers_resultats = []
        QApplication.processEvents()
        
        url_entreprise = "https://recherche-entreprises.api.gouv.fr/search"
        code_naf_selectionne = self.combo_act.currentData()
        code_tranche_max = self.combo_eff.currentData()
        valeur_tri_max = TRANCHES_EFFECTIFS[code_tranche_max][0]

        # Format du code NAF attendu par l'API (avec un point, ex: "5610A" -> "56.10A")
        code_formate = None
        if code_naf_selectionne != "TOUS":
            if len(code_naf_selectionne) == 5 and code_naf_selectionne[2] != ".":
                code_formate = f"{code_naf_selectionne[:2]}.{code_naf_selectionne[2:]}"
            else:
                code_formate = code_naf_selectionne

        PER_PAGE = 25                 # Maximum autorisé par l'API (était 20, et surtout une seule page était lue)
        MAX_PAGES_PAR_COMMUNE = 40    # Garde-fou pour éviter un nombre excessif d'appels (ex: "TOUS" sur une grande ville)

        try:
            for idx, code_insee in enumerate(codes_insee_valides, 1):
                page = 1
                total_pages = 1

                # --- BOUCLE DE PAGINATION ---
                # L'ancien code ne lisait QUE la page 1 (per_page=20) : au-delà des 20
                # premiers résultats renvoyés par l'API pour une commune/activité donnée,
                # toute entreprise plus loin dans le classement (ex: VU-NGO à Rouen en
                # 56.10A) était silencieusement ignorée. On parcourt maintenant toutes
                # les pages disponibles (total_pages renvoyé par l'API).
                while page <= total_pages and page <= MAX_PAGES_PAR_COMMUNE:
                    suffixe_page = f" (page {page}/{total_pages})" if total_pages > 1 else ""
                    self.result_area.append(
                        f"Commune {idx}/{len(codes_insee_valides)} — INSEE {code_insee}{suffixe_page}...")
                    QApplication.processEvents()

                    params = {
                        "per_page": PER_PAGE,
                        "page": page,
                        "code_commune": code_insee,
                    }
                    if code_formate:
                        params['activite_principale'] = code_formate

                    response = requests.get(url_entreprise, params=params, timeout=10)

                    if response.status_code == 429:
                        attente = float(response.headers.get("Retry-After", 2))
                        self.result_area.append(f"   Limite de débit de l'API atteinte, pause de {attente:.0f}s...")
                        QApplication.processEvents()
                        time.sleep(attente)
                        continue  # on retente la même page après la pause

                    if response.status_code != 200:
                        self.result_area.append(
                            f"   Erreur API ({response.status_code}) sur cette page — commune ignorée pour la suite.")
                        break

                    data = response.json()
                    total_pages = data.get("total_pages") or 1
                    resultats_bruts = data.get("results", [])
                    
                    for ent in resultats_bruts:
                        # --- SÉLECTION DU/DES BON(S) ÉTABLISSEMENT(S) ---
                        # "matching_etablissements" contient les établissements qui ont
                        # réellement satisfait le filtre géographique (code_commune) : si
                        # l'établissement situé dans la commune recherchée est un
                        # établissement secondaire, c'est SON adresse qu'on veut afficher,
                        # pas celle du siège social (qui peut être ailleurs).
                        etablissements_candidats = ent.get("matching_etablissements") or []
                        if not etablissements_candidats:
                            # Repli : aucun établissement "matché" renvoyé (rare, ex. recherche
                            # directe par SIREN) -> on utilise le siège par défaut.
                            etablissements_candidats = [ent.get("siege", {})]

                        # IMPORTANT : le paramètre 'activite_principale' de l'API ne filtre
                        # que le NAF de L'UNITÉ LÉGALE, jamais celui de ses établissements
                        # (c'est documenté dans l'OpenAPI de l'API). Une entreprise peut donc
                        # être retournée même si l'établissement situé dans la commune a un
                        # NAF différent. On re-filtre nous-mêmes ici pour ne garder que
                        # l'établissement dont le NAF PROPRE correspond vraiment au secteur
                        # demandé (c'est ce qui manquait pour retrouver VU-NGO en 56.10A).
                        if code_naf_selectionne != "TOUS":
                            filtres = [
                                e for e in etablissements_candidats
                                if (e.get("activite_principale") or "").replace(".", "") == code_naf_selectionne
                            ]
                            if filtres:
                                etablissements_candidats = filtres
                            # Si aucun établissement ne porte exactement ce NAF (cas limite),
                            # on garde la liste d'origine plutôt que de perdre le résultat.

                        tranche_ent = ent.get("tranche_effectif_salarie", "00")
                        if not tranche_ent or tranche_ent == "NN": 
                            tranche_ent = "00"
                        valeur_tri_ent = TRANCHES_EFFECTIFS.get(tranche_ent, (0, ""))[0]
                        
                        if code_tranche_max != "TOUS" and valeur_tri_ent > valeur_tri_max:
                            continue 

                        # Dirigeant principal (Gérant/Président en priorité) — calculé une
                        # seule fois par entreprise (le dirigeant est attaché à l'unité légale,
                        # pas à un établissement en particulier).
                        dirigeant_prenom, dirigeant_nom, dirigeant_qualite = extraire_dirigeant_principal(ent)

                        # Une même entreprise peut avoir plusieurs établissements pertinents
                        # (ex: deux enseignes du même type dans la même commune) -> une ligne
                        # de résultat par établissement, dédupliquée par SIRET.
                        for etab in etablissements_candidats:
                            siret_cible = etab.get("siret", "")
                            if not siret_cible:
                                continue

                            adresse_cible = etab.get("adresse") or \
                                f"{etab.get('code_postal', '')} {etab.get('libelle_commune', '')}".strip()

                            raw_naf = (etab.get("activite_principale") or ent.get("activite_principale", "")).replace(".", "")
                            libelle_activite = LISTE_NAF_SELECTION.get(
                                raw_naf, ent.get("libelle_activite_principale", "Inconnue"))

                            entree = dict(ent)
                            entree["adresse_complete_clean"] = adresse_cible
                            entree["siret_etablissement_clean"] = siret_cible
                            entree["libelle_effectif_clean"] = TRANCHES_EFFECTIFS.get(tranche_ent, (0, "Inconnu"))[1]
                            entree["libelle_activite_clean"] = libelle_activite
                            entree["dirigeant_prenom_clean"] = dirigeant_prenom
                            entree["dirigeant_nom_clean"] = dirigeant_nom
                            entree["dirigeant_qualite_clean"] = dirigeant_qualite

                            if entree["siret_etablissement_clean"] not in [e.get("siret_etablissement_clean") for e in self.derniers_resultats]:
                                self.derniers_resultats.append(entree)

                    page += 1
                    time.sleep(0.15)  # reste sous la limite de 7 requêtes/seconde imposée par l'API
            
            if not self.derniers_resultats:
                self.result_area.setText("Aucun résultat trouvé avec vos critères.")
            else:
                self.btn_csv.setEnabled(True)
                affichage = f"Extraction terminée ! Nombre total d'entreprises collectées : {len(self.derniers_resultats)}\n"
                affichage += "="*70 + "\n\n"
                
                for i, ent in enumerate(self.derniers_resultats, 1):
                    affichage += f"{i}. {ent.get('nom_complet', 'Nom inconnu')}\n"
                    affichage += f"   SIRET : {ent.get('siret_etablissement_clean')} | Effectif : {ent.get('libelle_effectif_clean')}\n"
                    affichage += f"   Activité : {ent.get('libelle_activite_clean')}\n"
                    affichage += f"   Adresse : {ent.get('adresse_complete_clean')}\n"
                    dirigeant_prenom = ent.get('dirigeant_prenom_clean', '')
                    dirigeant_nom = ent.get('dirigeant_nom_clean', '')
                    if dirigeant_nom:
                        qualite = ent.get('dirigeant_qualite_clean', '')
                        affichage += f"   Dirigeant : {dirigeant_prenom} {dirigeant_nom} ({qualite})\n"
                    affichage += "-"*70 + "\n"
                self.result_area.setText(affichage)
                
        except requests.exceptions.RequestException as e:
            self.result_area.setText(f"Erreur réseau : {str(e)}")
        finally:
            self.btn_search.setEnabled(True)

    def exporter_csv(self):
        if not self.derniers_resultats: return
        
        # 1. Extraction et nettoyage du nom de la commune centre
        saisie_commune = self.input_commune.text().strip()
        nom_commune = saisie_commune.split(" (")[0] if " (" in saisie_commune else saisie_commune
        
        # 2. Extraction du rayon propre (ex: "10 km" depuis "10 km")
        choix_rayon = self.combo_rayon.currentText()
        rayon_str = choix_rayon.split(" ")[0] + "_Km" # Donne "0_Km", "5_Km", "10_Km", etc.
        
        # 3. Extraction de l'activité sélectionnée
        code_act = self.combo_act.currentData()
        nom_activite = LISTE_NAF_SELECTION.get(code_act, "Toutes_Activites")
        
        # 4. Construction du nom avec le format demandé : Entreprises-Commune_Rayon_Activite
        nom_propose = f"Entreprises-{nom_commune}_{rayon_str}_{nom_activite}"
        
        # Nettoyage des caractères interdits par les systèmes de fichiers et remplacement des espaces
        nom_propose = re.sub(r'[\\/*?:"<>|]', "", nom_propose).replace(" ", "_")
        
        # Ouverture de la boîte de dialogue avec le nom pré-rempli
        fichier, _ = QFileDialog.getSaveFileName(
            self, 
            "Sauvegarder CSV", 
            f"{nom_propose}.csv", 
            "CSV (*.csv)"
        )
        
        if fichier:
            try:
                with open(fichier, mode='w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow(["Nom", "SIREN", "SIRET", "Activité (Libellé)", "Adresse",
                                      "Tranche Effectif", "Dirigeant Prénom", "Dirigeant Nom",
                                      "Dirigeant Qualité"])
                    for ent in self.derniers_resultats:
                        writer.writerow([
                            ent.get("nom_complet", ""), ent.get("siren", ""), ent.get("siret_etablissement_clean", ""),
                            ent.get("libelle_activite_clean", ""),
                            ent.get("adresse_complete_clean", ""), ent.get("libelle_effectif_clean", ""),
                            ent.get("dirigeant_prenom_clean", ""), ent.get("dirigeant_nom_clean", ""),
                            ent.get("dirigeant_qualite_clean", ""),
                        ])
                QMessageBox.information(self, "Succès", "Fichier CSV exporté avec succès.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = EntrepriseSearchApp()
    fenetre.show()
    sys.exit(app.exec())