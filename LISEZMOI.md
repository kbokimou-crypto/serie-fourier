# Série de Fourier – modélisation et prédiction d'une suite

## Le modèle

Le programme cherche l'équation

    u(n) = c0 + c1·n (+ c2·n²)  +  Σ  R_k · cos(2π·n / T_k + φ_k)

- **c0, c1, c2** : la tendance (constante, linéaire ou quadratique) ;
- **T_k** : période du k-ième cycle (en nombre de termes) ;
- **R_k** : son amplitude ; **φ_k** : sa phase (radians).

Étapes du calcul :
1. on retire la tendance par moindres carrés ;
2. la FFT (transformée de Fourier) du reste donne les périodes dominantes ;
3. chaque période est affinée, puis tous les coefficients sont recalculés
   ensemble par moindres carrés.

Prolonger cette équation pour n > N donne la **prédiction**.

## Utilisation

1. **Ouvrir un fichier CSV** : les nombres doivent être dans la colonne A
   (une ligne d'en-tête est acceptée ; séparateur `;` ou `,` ; virgule décimale acceptée).
2. Choisir le **nombre de termes de Fourier**, la **tendance**, et le **nombre de termes à prédire**,
   puis cliquer sur **Calculer le modèle**.
3. **Ajuster les coefficients** dans le tableau :
   - modifier une valeur puis Entrée → le graphique se met à jour ;
   - flèches ↑/↓ dans un champ : ±1 % (±0,05 rad pour la phase) ;
   - décocher « Actif » pour retirer un terme, ✕ pour le supprimer, « + Ajouter un terme » ;
   - **Réajuster R et φ** : garde vos périodes T et recalcule au mieux le reste.
4. **Termes gardés pour tester** : met de côté les derniers termes, ajuste le modèle sans eux,
   et mesure l'erreur de prédiction sur ces termes. C'est la meilleure façon de savoir
   si la prédiction est fiable.
5. **Exporter en CSV** : n, valeur observée, valeur du modèle et prédictions (format Excel français),
   avec l'équation en dernière ligne.

Le graphique du bas montre le spectre : les pics sont les périodes présentes dans la suite,
les traits rouges celles retenues par le modèle.

## Limite importante

Une série de Fourier ne prédit bien que les suites qui ont un comportement **répétitif**
(saisonnier, cyclique) autour d'une tendance régulière. Pour une suite sans cycle
(hasard, marche aléatoire, cours de bourse…), l'ajustement peut être excellent sur les
données connues et la prédiction fausse. Utilisez le test sur les derniers termes pour le vérifier,
et préférez peu de termes de Fourier : trop de termes « apprennent » le bruit.

## Fabriquer le programme Windows (.exe)

### Sur un PC Windows
1. Installer Python 3.10 ou plus récent depuis https://www.python.org
   (cocher **Add python.exe to PATH**).
2. Double-cliquer sur **build_exe.bat**.
3. Le programme est créé dans `dist\SerieFourier.exe` (un seul fichier, aucune installation nécessaire).
4. Facultatif : si **Inno Setup** (https://jrsoftware.org/isinfo.php) est installé, le script crée aussi
   l'installateur `Output\SerieFourier_Setup.exe` (raccourcis menu Démarrer / Bureau, désinstallation).

### Sans PC Windows : GitHub Actions
Déposer ce dossier dans un dépôt GitHub : le fichier `.github/workflows/build-windows.yml`
fabrique automatiquement l'exe et l'installateur sur un serveur Windows.
Ils se téléchargent dans l'onglet **Actions** → dernière exécution → **Artifacts**.

### Lancer sans fabriquer d'exe
    pip install numpy matplotlib
    python fourier_app.py  [fichier.csv]

## Fichiers
- `fourier_app.py` : l'interface graphique
- `fourier_model.py` : le calcul (lecture CSV, FFT, moindres carrés)
- `exemple_suite.csv` : une suite d'exemple (tendance + cycles de 12 et 6 termes + bruit)
- `build_exe.bat`, `installer.iss`, `requirements.txt`, `.github/workflows/build-windows.yml` : fabrication de l'exe
