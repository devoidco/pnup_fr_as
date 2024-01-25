import argparse
import os
import pickle
from pathlib import Path
import datetime
import json
import face_recognition
from decimal import Decimal
from pymongo import MongoClient
from bson.objectid import ObjectId
from sshtunnel import SSHTunnelForwarder

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

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def load_encodings(encodings_path):
    with encodings_path.open(mode="rb") as f:
        encodings = pickle.load(f)
    return encodings

def recognize_faces(image_path, encodings):
    image = face_recognition.load_image_file(image_path)
    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)

    results = []

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(
            [data["encoding"] for data in encodings],
            face_encoding
        )

        date = datetime.datetime.now().date()
        time = datetime.datetime.now().strftime("%H:%M:%S")

        if any(matches):
            face_distances = face_recognition.face_distance([data["encoding"] for data in encodings], face_encoding)
            min_distance = min(face_distances)
            min_distance_index = face_distances.argmin()

            if matches[min_distance_index]:
                matched_nim = encodings[min_distance_index]["nim"]
                matched_name = encodings[min_distance_index]["nama_lengkap"]
                accuracy = Decimal((1 - min_distance) * 100)
                print(accuracy)
                if accuracy >= 75:
                    result = {
                        "nama_lengkap": matched_name,
                        "nim": matched_nim,
                        "tanggal": str(date),
                        "jam": str(time),
                        "akurasi": accuracy
                    }

                    results.append(result)
        else:
            result = {
                "nama_lengkap": "Unknown",
                "nim": "",
                "tanggal": str(date),
                "jam": str(time),
                "akurasi": Decimal(0.0)
            }

            results.append(result)

    return results

# Fungsi untuk menyimpan hasil ke database MySQL
def save_to_database(results):
    menit_toleransi_terlambat = 10
    current_date = datetime.datetime.now().date()
    current_time = datetime.datetime.now().strftime("%H.%M")
    hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    nama_lengkap = ""
    nim = ""
    jam_masuk_mhs = ""
    jam_pulang_mhs = ""
    matkul = ""
    kelas = ""
    current_hari = ""
    status = "Kosong"

    print(results)
    for result in results:
        nama_lengkap = str(result["nama_lengkap"])
        nim = str(result["nim"])
        day = datetime.datetime.today().weekday()
        
        # print("get data mhs")
        data_mhs = collection3.find({"nim": str(result["nim"])})
        if not data_mhs:
            print("Data mahasiswa tidak cocok")
        kelas = str(data_mhs[0]['kelas'])
        current_hari = str(hari[day])
        # print(data_mhs[0])

        data_matkul = collection2.find({"pembagian.kelas": kelas, "pembagian.hari": current_hari})
        if not data_matkul:
            print("Data matkul tidak cocok")

        for row in data_matkul:
            print(row)
            matkul = row["matakuliah"]

            # Minimum jam masuk
            time_str = row['pembagian'][0]['jamMasuk']
            time_object = datetime.datetime.strptime(time_str, '%H.%M').time()
            min_time = time_object.strftime("%H.%M")

            # Maksimum jam Masuk
            datetime_with_time = datetime.datetime.combine(current_date, time_object)
            time_toleransi = datetime_with_time + datetime.timedelta(minutes=menit_toleransi_terlambat)
            max_time = time_toleransi.strftime("%H.%M")

            if (current_time >= min_time and current_time <= max_time) :
                jam_masuk_mhs = current_time
                status = "masuk"
            
            # Minimum jam pulang
            time_str = row['pembagian'][0]['jamPulang']
            time_object = datetime.datetime.strptime(time_str, '%H.%M').time()
            min_time = time_object.strftime("%H.%M")

            # Maksimum jam pulang
            datetime_with_time = datetime.datetime.combine(current_date, time_object)
            time_toleransi = datetime_with_time + datetime.timedelta(minutes=menit_toleransi_terlambat)
            max_time = time_toleransi.strftime("%H.%M")

            if (current_time >= min_time and current_time <= max_time) :
                jam_pulang_mhs = current_time
                status = "pulang"
            
            # cek jika sudah absen
            # next feature, harusnya hanya akan terabsen satu kali karena proses pengiriman ke databasenya lumayan lama

            print(status)
            if (status == "masuk") :
                document = {
                    "nama_lengkap": nama_lengkap,
                    "nim": nim,
                    "kelas": kelas,
                    "matkul": matkul,
                    "hari": str(current_hari),
                    "tanggal": str(current_date),
                    "jam": jam_masuk_mhs,
                    "status": "masuk"
                }
                result_query = collection4.insert_one(document)
                if result_query.inserted_id:
                    print("Berhasil Terabsen")
                else:
                    print('Gagal Terabsen')
            elif (status == "pulang") :
                document = {
                    "nama_lengkap": nama_lengkap,
                    "nim": nim,
                    "kelas": kelas,
                    "matkul": matkul,
                    "hari": str(current_hari),
                    "tanggal": str(current_date),
                    "jam": jam_pulang_mhs,
                    "status": "pulang"
                }
                result_query = collection4.insert_one(document)
                if result_query.inserted_id:
                    print("Berhasil Terabsen")
                else:
                    print('Gagal Terabsen')
    print("Proceed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Face Recognition Testing Script")
    parser.add_argument("--image_dir", metavar="IMAGE_DIR", default="validation", help="Directory containing the test images")

    args = parser.parse_args()

    DEFAULT_ENCODINGS_PATH = Path("output/encodings.pkl")
    image_dir = Path(args.image_dir)

    if not image_dir.exists() or not image_dir.is_dir():
        print(f"Directory '{args.image_dir}' does not exist.")
        exit()

    image_paths = list(image_dir.glob("*"))

    if not image_paths:
        print(f"No images found in directory '{args.image_dir}'.")
        exit()

    encodings = load_encodings(DEFAULT_ENCODINGS_PATH)

    results_all = []

    for image_path in image_paths:
        if image_path.is_file():
            results = recognize_faces(image_path, encodings)
            results_all.extend(results)

    output_path = "output/results.json"

    filtered_results = [result for result in results_all if result["akurasi"] >= 75]

    with open(output_path, "w") as f:
        json.dump(filtered_results, f, indent=4, default=decimal_default)

    save_to_database(filtered_results)

    for image_path in image_paths:
        if image_path.is_file():
            os.remove(image_path)
