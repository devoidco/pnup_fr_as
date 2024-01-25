import argparse
import datetime
import pickle
import json
from collections import Counter
from pathlib import Path
import os
import face_recognition
from sshtunnel import SSHTunnelForwarder
from pymongo import MongoClient
from bson.objectid import ObjectId
from PIL import Image, ImageDraw

DEFAULT_ENCODINGS_PATH = Path("output/encodings.pkl")

server_ip = "192.168.31.41";
server = SSHTunnelForwarder(
    server_ip,
    ssh_username="1bnz",
    ssh_password="Al-mulk67",
    remote_bind_address=('127.0.0.1', 27017)
)

server.start()

client = MongoClient('mongodb://admin:123@'+ server_ip +':27017/')
db = client['absen_face_recognition']
collection1 = db['matakuliah']
collection2 = db['matkul']
collection3 = db['mahasiswa']
collection4 = db['logabsen']

def create_directories_if_not_exists():
    Path("training").mkdir(parents=True, exist_ok=True)
    Path("output").mkdir(parents=True, exist_ok=True)


def encode_known_faces():
    data = []
    for filepath in Path("training").glob("*/*"):
        id = filepath.parent.name
        image = face_recognition.load_image_file(filepath)

        face_locations = face_recognition.face_locations(image)
        face_encodings = face_recognition.face_encodings(image, face_locations)

        for encoding in face_encodings:
            data.append({"id": id, "encoding": encoding, "gender": None, "nim": None, "nama_lengkap": None})

    with DEFAULT_ENCODINGS_PATH.open(mode="wb") as f:
        pickle.dump(data, f)


def add_training_data(folder_name, nim=None, nama_lengkap=None, gender=None):
    folder_path = Path("training") / folder_name

    if folder_path.exists() and folder_path.is_dir():
        with DEFAULT_ENCODINGS_PATH.open(mode="rb") as f:
            existing_data = pickle.load(f)

        for filepath in folder_path.glob("*"):
            image = face_recognition.load_image_file(filepath)

            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)

            for encoding in face_encodings:
                existing_data.append({"id": folder_name, "encoding": encoding, "gender": gender, "nim": nim, "nama_lengkap": nama_lengkap})

        with DEFAULT_ENCODINGS_PATH.open(mode="wb") as f:
            pickle.dump(existing_data, f)
    else:
        print(f"Folder '{folder_name}' does not exist in the 'training' directory.")


if __name__ == "__main__":
    create_directories_if_not_exists()

    parser = argparse.ArgumentParser(description="Face Recognition Training Script")
    parser.add_argument("--train", action="store_true", help="Perform training on all images in the 'training' folder")
    parser.add_argument("--add", metavar="FOLDER_NAME", help="Add training data for a specific folder")
    parser.add_argument("--nim", metavar="nim", help="Specify NIM for the added training data")
    parser.add_argument("--nama_lengkap", metavar="nama_lengkap", help="Specify name for the added training data")
    parser.add_argument("--gender", metavar="GENDER", help="Specify gender for the added training data")

    args = parser.parse_args()

    if args.train:
        encode_known_faces()
        print("Training completed.")

    if args.add:
        add_training_data(args.add, args.nim, args.nama_lengkap, args.gender)
        print(f"Training data added for folder '{args.add}' with NIM '{args.nim}', Nama Lengkap '{args.nama_lengkap}', and gender '{args.gender}'.")
