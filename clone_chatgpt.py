import time
# from datetime import datetime
from flask import Flask, request, render_template, jsonify, flash, session, redirect, url_for
from googleapiclient.discovery import build
# import vlc
import speech_recognition as sr
import re
import requests
import pymysql
import nltk
import pyttsx3
import os
from flask_bcrypt import Bcrypt
# from functools import wraps
from werkzeug.utils import secure_filename
# from PIL import Image


# import bcrypt
# from werkzeug.security import generate_password_hash, check_password_hash

# Télécharger les ressources nécessaires pour nltk (à exécuter une seule fois)
nltk.download('punkt')
nltk.download('stopwords')

# Générer une clé secrète aléatoire


def generate_secret_key():
    return os.urandom(24)


app = Flask(__name__)

bcrypt = Bcrypt(app)
# Définir la clé secrète de l'application Flask
app.secret_key = generate_secret_key()

# Configuration de la base de données MySQL
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    db='bd_final_chat',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()


# Configuration de la clé API YouTube
youtube_api_key = 'AIzaSyB6-ZeoQYbdLi5scEbmpQRX-CJ_acupzlQ'

# Initialisation du client YouTube API
youtube = build('youtube', 'v3', developerKey=youtube_api_key)

# Variable globale pour le lecteur VLC
vlc_player = None

# URL et headers pour l'API Coze
coze_url = "https://api.coze.com/open_api/v2/chat"
coze_headers = {
    "Authorization": "Bearer pat_bwdJXkKdHjJ4v4mj04kTHm23p3U2s5CJFXmaXFnbK5ItsBQlrF2Z1BvH85s11wSS",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Host": "api.coze.com",
    "Connection": "keep-alive"
}


######################## PROFIL UTILISATEUR ##############


# Configuration du dossier d'upload pour les images de profil
UPLOAD_FOLDER_PARENT = 'static/uploads/images_profil_parent'
app.config['UPLOAD_FOLDER_PARENT'] = UPLOAD_FOLDER_PARENT

# Liste des extensions de fichiers autorisées pour les images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/update_profile_image', methods=['POST'])
def update_profile_image():
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    if 'profileImage' not in request.files:
        flash('Aucun fichier trouvé', 'danger')
        return redirect(url_for('profil'))

    file = request.files['profileImage']

    if file.filename == '':
        flash('Aucun fichier sélectionné', 'danger')
        return redirect(url_for('profil'))

    if file and allowed_file(file.filename):
        if not os.path.exists(app.config['UPLOAD_FOLDER_PARENT']):
            os.makedirs(app.config['UPLOAD_FOLDER_PARENT'])

        # Générer un nom de fichier unique en ajoutant un timestamp
        timestamp = int(time.time())
        filename = secure_filename(file.filename)
        unique_filename = f"{filename}_{timestamp}"

        file_path = os.path.join(
            app.config['UPLOAD_FOLDER_PARENT'], unique_filename)
        file.save(file_path)

        # Utiliser le chemin complet normaliser vers l'image dans le dossier statique
        full_image_path = os.path.normpath(os.path.join(
            'uploads/images_profil_parent', unique_filename)).replace('\\', '/')

        user_id = session.get('user_id')

        if user_id is not None:
            # Connexion à la base de données
            connection = pymysql.connect(host='localhost',
                                         user='root',
                                         password='',
                                         db='bd_final_chat',
                                         charset='utf8mb4',
                                         cursorclass=pymysql.cursors.DictCursor)

            try:
                with connection.cursor() as cursor:
                    # Mettre à jour le chemin de l'image de profil dans la base de données
                    sql = "UPDATE users SET profileImage = %s WHERE id = %s"
                    cursor.execute(sql, (full_image_path, user_id))
                    connection.commit()
                    flash('Photo de profil mis à jour avec succès!', 'success')
            except pymysql.Error as e:
                flash(
                    f'Erreur lors de la mise à jour du profil : {str(e)}', 'danger')
            finally:
                connection.close()

        else:
            flash('Erreur ID de l\'utilisateur', 'danger')

    return redirect(url_for('profil'))


@app.route('/profil', methods=['GET', 'POST'])
def profil():
    if 'user_id' in session:
        user_id = session['user_id']

        # Connexion à la base de données
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='bd_final_chat',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        try:
            with connection.cursor() as cursor:
                # Récupérer les informations de l'utilisateur
                sql = "SELECT nom, email, username, profileImage FROM users WHERE id = %s"
                cursor.execute(sql, (user_id,))
                user = cursor.fetchone()

                if request.method == 'POST':
                    # Mettre à jour les informations de l'utilisateur
                    nom = request.form['nom']
                    username = request.form['username']
                    email = request.form['email']
                    password = request.form['password']

                    if password:
                        hashed_password = bcrypt.generate_password_hash(
                            password).decode('utf-8')
                        update_sql = "UPDATE users SET nom = %s, username = %s, email = %s, password = %s WHERE id = %s"
                        cursor.execute(
                            update_sql, (nom, username, email, hashed_password, user_id))
                    else:
                        update_sql = "UPDATE users SET nom = %s, username = %s, email = %s WHERE id = %s"
                        cursor.execute(
                            update_sql, (nom, username, email, user_id))

                    connection.commit()
                    flash('Profil mis à jour avec succès', 'success')
                    return redirect(url_for('profil'))

                if user:
                    return render_template('users/profil.html', user=user)
                else:
                    flash('Utilisateur non trouvé', 'danger')
                    return redirect(url_for('connexion'))

        except pymysql.Error as e:
            flash(
                f'Erreur lors de la récupération des informations de l\'utilisateur : {str(e)}', 'danger')
            return redirect(url_for('connexion'))

        finally:
            connection.close()

    else:
        return redirect(url_for('connexion'))

########### FIN PROFIL UTILISATEUR #########


@app.route('/')
def index():
    return render_template('accueil.html')

# Route de inscription


@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    # ? Connection à ma db
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='bd_final_chat',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    # ? Utilisons un curseur pour exécuter nos requêtes SQL
    cursor = conn.cursor()

    if request.method == 'POST':
        nom = request.form['nom']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Les mots de passe ne sont pas identiques !", 'info')
            return redirect(url_for('inscription'))

        select_query = "SELECT id FROM users WHERE email = %s"
        cursor.execute(select_query, (email,))
        user_exist = cursor.fetchone()

        if user_exist:
            flash(
                "Cet utilisateur existe déjà. Veuillez entrer un autre email.", 'danger')
        else:
            hashed_password = bcrypt.generate_password_hash(
                password).decode('utf-8')
            print(f"Mot de passe haché : {hashed_password}")

            # Chemin par défaut pour l'image de profil
            default_profile_image = 'uploads/images_profil_parent/bot_avatar.jpg'

            insert_query = "INSERT INTO users (nom, username, email, password, profileImage) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(insert_query, (nom, username, email,
                           hashed_password, default_profile_image))
            conn.commit()

            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user_id = cursor.fetchone()['id']

            session['user_id'] = user_id

            flash('Inscription réussie! Connectez-vous maintenant.', 'success')
            return redirect(url_for('connexion'))

    return render_template('users/inscrip.html')


# Route de connexion
@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    # ? Connection à ma db
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='bd_final_chat',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    # ? Utilisons un curseur pour exécuter nos requêtes SQL
    cursor = conn.cursor()

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        select_query = "SELECT id, nom, username, email, password FROM users WHERE email = %s"
        cursor.execute(select_query, (email,))
        user = cursor.fetchone()

        if user:
            stored_password = user['password']
            print(f"Mot de passe stocké : {stored_password}")
            if bcrypt.check_password_hash(stored_password, password):
                session['user_id'] = user['id']
                flash('Connexion réussie!', 'success')
                return redirect(url_for('interface'))
            else:
                flash('Mot de passe incorrect', 'danger')
        else:
            flash('Email incorrect', 'danger')

    return render_template('users/cone.html')


@app.route('/Interface')
def interface():
    if 'user_id' in session:
        user_id = session['user_id']

        # Connexion à la base de données
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='bd_final_chat',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        try:
            with connection.cursor() as cursor:
                sql = "SELECT nom, email, profileImage FROM users WHERE id = %s"
                cursor.execute(sql, (user_id,))
                user = cursor.fetchone()

                if user:
                    return render_template('clone_chatgpt.html', user=user)
                else:
                    flash('Utilisateur non trouvé', 'danger')
                    return redirect(url_for('connexion'))

        except pymysql.Error as e:
            flash(
                f'Erreur lors de la récupération des informations de l\'utilisateur : {str(e)}', 'danger')
            return redirect(url_for('connexion'))

        finally:
            connection.close()

    else:
        return redirect(url_for('connexion'))


# Route de déconnexion

# @app.route('/Déconnexion', methods=['GET', 'POST'])
# def deconnexion():
#     if request.method == 'POST':
#         if 'confirm' in request.form and request.form['confirm'] == 'yes':
#             # Supprimer l'ID de session pour déconnecter l'utilisateur
#             session.pop('user_id', None)
#             flash('Déconnexion réussie!', 'success')
#             return redirect(url_for('connexion'))
#     # Si la méthode n'est pas POST ou si le formulaire de confirmation n'a pas été soumis, rediriger vers l'interface
#     return redirect(url_for('interface'))
@app.route('/Déconnexion', methods=['GET', 'POST'])
def deconnexion():
    if request.method == 'POST':
        if 'confirm' in request.form and request.form['confirm'] == 'yes':
            # Supprimer l'ID de session pour déconnecter l'utilisateur
            session.pop('user_id', None)
            flash('Déconnexion réussie!', 'success')
            # Rediriger vers la page de connexion
            return redirect(url_for('connexion'))
    # Si la méthode n'est pas POST ou si le formulaire de confirmation n'a pas été soumis, rediriger vers l'interface
    if 'user_id' in session:
        user_id = session['user_id']

        # Connexion à la base de données
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='bd_final_chat',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        try:
            with connection.cursor() as cursor:
                sql = "SELECT nom, email, profileImage FROM users WHERE id = %s"
                cursor.execute(sql, (user_id,))
                user = cursor.fetchone()

                if user:
                    return render_template('clone_chatgpt.html', user=user)
                else:
                    flash('Utilisateur non trouvé', 'danger')
                    return redirect(url_for('connexion'))

        except pymysql.Error as e:
            flash(
                f'Erreur lors de la récupération des informations de l\'utilisateur : {str(e)}', 'danger')
            return redirect(url_for('connexion'))

        finally:
            connection.close()

    else:
        return redirect(url_for('connexion'))


@app.route('/confirmation_deconnexion')
def deco():
    if 'user_id' in session:
        user_id = session['user_id']

        # Connexion à la base de données
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='bd_final_chat',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        try:
            with connection.cursor() as cursor:
                sql = "SELECT nom, email, profileImage FROM users WHERE id = %s"
                cursor.execute(sql, (user_id,))
                user = cursor.fetchone()

                if user:
                    return render_template('users/deco.html', user=user)
                else:
                    flash('Utilisateur non trouvé', 'danger')
                    return redirect(url_for('connexion'))

        except pymysql.Error as e:
            flash(
                f'Erreur lors de la récupération des informations de l\'utilisateur : {str(e)}', 'danger')
            return redirect(url_for('connexion'))

        finally:
            connection.close()

    else:
        return redirect(url_for('connexion'))


# @app.route('/confirmation_deconnexion')
# def deco():
#     return render_template('users/deco.html')


# Route pour le chat, prend en charge à la fois l'entrée vocale et textuelle
@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.form['user_input']
    user_id = 1  # Utilisez l'ID utilisateur réel

    # Vérifier s'il s'agit d'une commande vocale pour jouer/arrêter la musique/vidéo
    if re.search(r'joue.*musique|vidéo', user_input, re.IGNORECASE):
        query = user_input.replace("joue", "").strip()
        response = play_youtube_video(query)
    elif re.search(r'arrête.*musique|vidéo', user_input, re.IGNORECASE):
        response = stop_youtube_video()
    elif user_input.startswith("file:") and len(user_input.split(':')) > 1:
        file_path = user_input.split(':')[1]
        response = process_file_message(file_path, user_id)
    else:
        # Si ce n'est pas une commande pour la musique/vidéo, traiter comme saisie texte normale
        response = process_user_input(user_input, user_id)

    return jsonify({'response': response})


# Fonction pour traiter l'entrée utilisateur (textuelle ou vocale) avec le chatbot
def process_user_input(user_input, user_id):
    # Traiter avec le chatbot et synthèse vocale
    bot_response = talk_to_daysie(user_input, user_id)
    return bot_response


# # URL et headers pour l'API Coze
# coze_url = "https://api.coze.com/open_api/v2/chat"
# coze_headers = {
#     "Authorization": "Bearer pat_bwdJXkKdHjJ4v4mj04kTHm23p3U2s5CJFXmaXFnbK5ItsBQlrF2Z1BvH85s11wSS",
#     "Content-Type": "application/json",
#     "Accept": "*/*",
#     "Host": "api.coze.com",
#     "Connection": "keep-alive"
# }
# # Fonction pour parler avec le chatbot et utiliser pyttsx3 pour la synthèse vocale


# def talk_to_daysie(user_input, user_id):
#     # ? Connection à ma db
#     conn = pymysql.connect(
#         host='localhost',
#         user='root',
#         password='',
#         db='bd_final_chat',
#         charset='utf8mb4',
#         cursorclass=pymysql.cursors.DictCursor
#     )

#     # ? Utilisons un curseur pour exécuter nos requêtes SQL
#     cursor = conn.cursor()
#     # Vérifier s'il y a une conversation existante pour l'utilisateur
#     cursor.execute(
#         "SELECT id FROM conversations WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
#     conversation = cursor.fetchone()

#     if not conversation:
#         # Insérer une nouvelle conversation
#         sql_insert_conversation = "INSERT INTO conversations (user_id, title) VALUES (%s, %s)"
#         conversation_data = (user_id, generate_conversation_title(user_input))
#         cursor.execute(sql_insert_conversation, conversation_data)
#         conn.commit()
#         conversation_id = cursor.lastrowid
#     else:
#         conversation_id = conversation['id']

#     # Insérer le message de l'utilisateur
#     save_conversation_to_database(user_input, 'user', conversation_id)

#     # Appel à l'API Coze
#     data = {
#         "conversation_id": str(conversation_id),
#         "bot_id": "7386626502815219717",  # Utilisez l'ID de votre bot ici
#         "user": "29032201862555",  # Utilisez l'ID de votre utilisateur ici
#         "query": user_input,
#         "stream": False
#     }

#     # Affichage des données envoyées pour debug
#     print(f"Sending request to Coze API: {data}")
#     response = requests.post(coze_url, headers=coze_headers, json=data)

#     # Affichage de la réponse pour debug
#     print(f"Response status code: {response.status_code}")
#     if response.status_code == 200:
#         response_json = response.json()
#         print(f"Response JSON: {response_json}")

#         if response_json.get('code') == 0:
#             messages = response_json.get('messages', [])
#             for message in messages:
#                 if message['type'] == 'answer':
#                     bot_response = message['content']
#                     save_conversation_to_database(
#                         bot_response, 'bot', conversation_id)

#                     # Synthèse vocale avec pyttsx3
#                     engine = pyttsx3.init()
#                     voices = engine.getProperty('voices')
#                     for voice in voices:
#                         if "female" in voice.name.lower():
#                             engine.setProperty('voice', voice.id)
#                             break
#                     engine.say(bot_response)
#                     engine.runAndWait()

#                     return bot_response

#             user_message = "Désolé, je n'ai pas de réponse pour cela."
#             save_conversation_to_database(user_message, 'bot', conversation_id)
#             return user_message
#         else:
#             error_message = response_json.get('msg', 'Erreur inconnue')
#             save_conversation_to_database(
#                 error_message, 'bot', conversation_id)
#             return error_message

#     else:
#         error_message = f"Erreur de communication avec Daysie: {response.text}"
#         save_conversation_to_database(error_message, 'bot', conversation_id)
#         return error_message

# Essayé d'avoir la reponse du bot ######################################""""


# URL et en-têtes pour l'API Coze
coze_url = 'https://api.coze.com/open_api/v2/chat'
coze_headers = {
    # Remplacez par votre jeton d'accès personnel
    'Authorization': 'Bearer pat_PEH0qwSNdOYL6y5P9w8d7KIMRHRW0uXvhHDLDMXmwAfWjHbI81Y25pFuJrD2ZVYc',
    'Content-Type': 'application/json',
    'Accept': '*/*',
    'Host': 'api.coze.com',
    'Connection': 'keep-alive'
}

# Fonction pour parler avec le chatbot et utiliser pyttsx3 pour la synthèse vocale


def talk_to_daysie(user_input, user_id):
    # Connection à la base de données
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='bd_final_chat',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    # Utilisation d'un curseur pour exécuter les requêtes SQL
    cursor = conn.cursor()
    # Vérifier s'il y a une conversation existante pour l'utilisateur
    cursor.execute(
        "SELECT id FROM conversations WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
    conversation = cursor.fetchone()

    if not conversation:
        # Insérer une nouvelle conversation
        sql_insert_conversation = "INSERT INTO conversations (user_id, title) VALUES (%s, %s)"
        conversation_data = (user_id, generate_conversation_title(user_input))
        cursor.execute(sql_insert_conversation, conversation_data)
        conn.commit()
        conversation_id = cursor.lastrowid
    else:
        conversation_id = conversation['id']

    # Insérer le message de l'utilisateur
    save_conversation_to_database(user_input, 'user', conversation_id)

    # Appel à l'API Coze
    data = {
        # Assurez-vous que ce soit une chaîne ou un nombre selon les spécifications
        "conversation_id": str(conversation_id),
        "bot_id": "7393176167115096070",  # Remplacez par l'ID de votre bot
        "user": "29032201862555",  # Assurez-vous que l'ID utilisateur est correct
        "query": user_input,
        "stream": False
    }

    # Affichage des données envoyées pour debug
    print(f"Sending request to Coze API: {data}")
    response = requests.post(coze_url, headers=coze_headers, json=data)

    # Affichage de la réponse pour debug
    print(f"Response status code: {response.status_code}")
    if response.status_code == 200:
        response_json = response.json()
        print(f"Response JSON: {response_json}")

        if response_json.get('code') == 0:
            messages = response_json.get('messages', [])
            for message in messages:
                if message['type'] == 'answer':
                    bot_response = message['content']
                    save_conversation_to_database(
                        bot_response, 'bot', conversation_id)

                    # Synthèse vocale avec pyttsx3
                    engine = pyttsx3.init()
                    voices = engine.getProperty('voices')
                    for voice in voices:
                        if "female" in voice.name.lower():
                            engine.setProperty('voice', voice.id)
                            break
                    engine.say(bot_response)
                    engine.runAndWait()

                    return bot_response

            user_message = "Désolé, je n'ai pas de réponse pour cela."
            save_conversation_to_database(user_message, 'bot', conversation_id)
            return user_message
        else:
            error_message = response_json.get('msg', 'Erreur inconnue')
            save_conversation_to_database(
                error_message, 'bot', conversation_id)
            return error_message

    else:
        error_message = f"Erreur de communication avec Daysie: {response.text}"
        save_conversation_to_database(error_message, 'bot', conversation_id)
        return error_message


# Essayé d'avoir la reponse du bot ######################################""""


# Fonction pour générer un titre de conversation
def generate_conversation_title(user_input):
    return "Conversation - " + user_input[:30]


# Fonction pour sauvegarder la conversation dans la base de données
def save_conversation_to_database(content, sender, conversation_id):
    sql_insert_message = "INSERT INTO messages (conversation_id, content, sender) VALUES (%s, %s, %s)"
    cursor.execute(sql_insert_message, (conversation_id, content, sender))
    conn.commit()


# Fonction pour jouer une vidéo YouTube
def play_youtube_video(query):
    global vlc_player
    if (vlc_player):
        vlc_player.stop()
    request = youtube.search().list(part="snippet", maxResults=1, q=query)
    response = request.execute()
    video_id = response['items'][0]['id']['videoId']
    return f"https://www.youtube.com/embed/{video_id}"


# Fonction pour arrêter la lecture de musique/vidéo
def stop_youtube_video():
    global vlc_player
    if (vlc_player):
        vlc_player.stop()
        vlc_player = None
        return "Musique/vidéo arrêtée."
    else:
        return "Aucune musique/vidéo n'est en cours de lecture."


# Fonction pour traiter le message de fichier
def process_file_message(file_path, user_id):
    # Insérer le message de l'utilisateur avec le fichier
    file_name = os.path.basename(file_path)
    user_input = f"file:{file_name}"
    cursor.execute(
        "SELECT id FROM conversations WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
    conversation = cursor.fetchone()

    if not conversation:
        # Insérer une nouvelle conversation
        sql_insert_conversation = "INSERT INTO conversations (user_id, title) VALUES (%s, %s)"
        conversation_data = (user_id, generate_conversation_title(user_input))
        cursor.execute(sql_insert_conversation, conversation_data)
        conn.commit()
        conversation_id = cursor.lastrowid
    else:
        conversation_id = conversation['id']

    save_conversation_to_database(user_input, 'user', conversation_id)

    # Déplacer le fichier téléchargé dans le répertoire de l'application
    uploaded_file_path = os.path.join(app.root_path, 'uploads', file_name)
    file_path.save(uploaded_file_path)

    # Mettre à jour l'interface utilisateur avec le fichier téléchargé
    return f"file:{file_name}"


# Route pour écouter l'entrée vocale
@app.route('/listen', methods=['POST'])
def listen():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Parlez maintenant...")
        audio = recognizer.listen(source)
    try:
        user_input = recognizer.recognize_google(audio, language='fr-FR')
        if re.search(r'joue.*musique|vidéo', user_input, re.IGNORECASE):
            query = user_input.replace("joue", "").strip()
            response = play_youtube_video(query)
        elif re.search(r'arrête.*musique|vidéo', user_input, re.IGNORECASE):
            response = stop_youtube_video()
        else:
            response = process_user_input(user_input, 1)
    except sr.UnknownValueError:
        response = "Je n'ai pas compris. Pouvez-vous répéter, s'il vous plaît ?"
    except sr.RequestError as e:
        response = f"Erreur du service de reconnaissance vocale : {e}"
    return jsonify({'response': response})


# Route pour récupérer les conversations de l'utilisateur
# @app.route('/get_conversations', methods=['GET'])
# def get_conversations():
#     user_id = 1  # Utilisez l'ID utilisateur réel
#     cursor.execute(
#         "SELECT id, title FROM conversations WHERE user_id = %s", (user_id,))
#     conversations = cursor.fetchall()
#     return jsonify(conversations)


# Route pour récupérer les messages d'une conversation spécifique
@app.route('/get_conversations', methods=['GET'])
def get_conversations():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify([])
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='bd_final_chat',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    # ? Utilisons un curseur pour exécuter nos requêtes SQL
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, title FROM conversations WHERE user_id = %s', (user_id,))
    conversations = cursor.fetchall()
    cursor.close()

    return jsonify(conversations)


@app.route('/get_messages/<int:conversation_id>', methods=['GET'])
def get_messages(conversation_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify([])

    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='bd_final_chat',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    # ? Utilisons un curseur pour exécuter nos requêtes SQL
    cursor = conn.cursor()
    # Ensure that the conversation belongs to the logged-in user
    cursor.execute(
        'SELECT id FROM conversations WHERE id = %s AND user_id = %s', (conversation_id, user_id))
    conversation = cursor.fetchone()
    if not conversation:
        return jsonify([])

    cursor.execute(
        'SELECT sender, content FROM messages WHERE conversation_id = %s', (conversation_id,))
    messages = cursor.fetchall()
    cursor.close()

    return jsonify(messages)


# Route lorsque je clique sur une conversation etant sur profil


# @app.route('/conversation/<int:conversation_id>', methods=['GET'])
# def conversation(conversation_id):
#     user_id = session.get('user_id')
#     if not user_id:
#         return redirect(url_for('connexion'))

#     conn = pymysql.connect(
#         host='localhost',
#         user='root',
#         password='',
#         db='bd_final_chat',
#         charset='utf8mb4',
#         cursorclass=pymysql.cursors.DictCursor
#     )

#     # ? Utilisons un curseur pour exécuter nos requêtes SQL
#     cursor = conn.cursor()
#     cursor.execute(
#         "SELECT id FROM conversations WHERE id = %s AND user_id = %s", (conversation_id, user_id))
#     conversation = cursor.fetchone()
#     if not conversation:
#         return "Unauthorized", 403

#     cursor.execute(
#         "SELECT content, sender FROM messages WHERE conversation_id = %s", (conversation_id,))
#     messages = cursor.fetchall()
#     cursor.execute(
#         "SELECT nom, profileImage FROM users WHERE id = %s", (user_id,))
#     user = cursor.fetchone()
#     cursor.close()
#     return render_template('clone_chatgpt.html', messages=messages, conversation_id=conversation_id, user=user)


@app.route('/conversation/<int:conversation_id>', methods=['GET'])
def conversation(conversation_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('connexion'))

    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='bd_final_chat',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM conversations WHERE id = %s AND user_id = %s", (conversation_id, user_id))
    conversation = cursor.fetchone()
    if not conversation:
        return "Unauthorized", 403

    cursor.execute(
        "SELECT content, sender FROM messages WHERE conversation_id = %s", (conversation_id,))
    messages = cursor.fetchall()
    cursor.execute(
        "SELECT nom, profileImage FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    return render_template('clone_chatgpt.html', messages=messages, conversation_id=conversation_id, user=user)


@app.route('/start_new_conversation', methods=['POST'])
def start_new_conversation():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('connexion'))

    data = request.get_json()
    conversation_title = data.get('title')
    if not conversation_title:
        return jsonify({'error': 'Titre de la conversation requis'}), 400

    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='bd_final_chat',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    # ? Utilisons un curseur pour exécuter nos requêtes SQL
    cursor = conn.cursor()
    sql_insert_conversation = "INSERT INTO conversations (user_id, title) VALUES (%s, %s)"
    cursor.execute(sql_insert_conversation, (user_id, conversation_title))
    conn.commit()
    conversation_id = cursor.lastrowid
    cursor.close()

    return jsonify({'conversation_id': conversation_id, 'title': conversation_title})


if __name__ == '__main__':
    app.run(debug=True)
