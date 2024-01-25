import pickle
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for
import os
import cv2
import time
import urllib.request
import numpy as np
import subprocess
from pymongo import MongoClient
from bson.objectid import ObjectId
from sshtunnel import SSHTunnelForwarder

server_ip = "192.168.140.41";
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

app = Flask(__name__)

# Konfigurasi folder statis
app.static_folder = 'templates/static'

# Load pickle data
pickle_file_path = Path("output/encodings.pkl")

try:
    with open(pickle_file_path, 'rb') as file:
        data = pickle.load(file)
except FileNotFoundError:
    data = None
    print("File pickle tidak ditemukan.")
except Exception as e:
    data = None
    print("Terjadi kesalahan saat membuka file pickle:", str(e))

# Global face_cascade variable
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
validation_folder = "validation"
      
@app.route('/')
def index():
    documents = db['logabsen'].find()
    return render_template('index.html', documents=documents)

@app.route('/mode')
def mode():
    return render_template('mode.html')

@app.route('/check_data')
def show_data():
    print(data)
    if data:
        unique_data = []
        seen = set()
        for item in data:
            print(item)
            key = (item['nama_lengkap'], item['nim'])
            if key not in seen:
                seen.add(key)
                unique_data.append(item)

        data_count = len(data)

        merged_data = []
        for item in unique_data:
            item['jumlah_data'] = data_count
            merged_data.append(item)

        return render_template('checkData.html', data=merged_data)
    else:
        return "Data not available."

@app.route('/enroll')
def enroll():
    return render_template('enroll.html')

@app.route('/capture', methods=['POST'])
def capture():
    folder_name = request.form['folder_name']
    num_images = int(request.form['num_images'])
    camera_url = request.form['camera_url']

    create_training_folder(folder_name)
    capture_images(folder_name, num_images=num_images, camera_url=camera_url)

    nim = request.form['nim']
    nama_lengkap = request.form['nama_lengkap']
    gender = request.form['gender']

    training_command = f'python3 trainingRev2.py --add {folder_name} --nim {nim} --nama_lengkap "{nama_lengkap}" --gender {gender}'
    os.system(training_command)

    document = {
        "nama_lengkap": str(nama_lengkap),
        "nim": str(nim),
        "kelas": "Edit Kelas",
    }
    result_query = collection3.insert_one(document)
    if result_query.inserted_id:
        print("Data Mahasiswa Berhasil Ditambahkan")
    else:
        print("Data Mahasiswa Gagal Ditambahkan")

    return "Data biometrik wajah mahasiswa berhasil tersimpan"

@app.route('/absensi_index', methods=['GET', 'POST'])
def absensi_index():
    if request.method == 'POST':
        url = request.form['url']
        create_validation_folder()
        capture_and_validate(url)
        return "Validation program exited. Restarting image capture and validation."
    return render_template('absensi.html')

@app.route('/tableMatakuliah')
def tableMatkul():
    # Get all documents from the matakuliah collection
    documents = collection1.find()

    # If there are no documents, return an empty list
    if not documents:
        return render_template('tabelMatakuliah.html', tableData=None)

    # Create a list to store the table data
    tableData = []

    # Iterate through the documents and add the data to the list
    for document in documents:
        tableData.append({
            "kodeMatakuliah": document['kode_matakuliah'],
            "namaMatakuliah": document['nama_matakuliah'],
            "hariMasuk": document['hari'],
            "jamMasuk": document['jam_masuk'],
            "jamKeluar": document['jam_keluar'],
            # Add the _id field for identifying each document
            "_id": str(document['_id'])
        })

    # Return the table data to the template
    return render_template('tabelMatakuliah.html', tableData=tableData)

@app.route('/deleteMatakuliah/<matkul_id>', methods=['GET', 'POST'])
def delete_matakuliah(matkul_id):
    # Convert matkul_id to ObjectId
    obj_id = ObjectId(matkul_id)

    # Delete document with the corresponding ID
    result = collection1.delete_one({'_id': obj_id})

    if result.deleted_count > 0:
        # Redirect to the tableMatkul page after deleting data
        return redirect(url_for('tableMatkul'))
    else:
        return 'Data tidak ditemukan'

@app.route('/editMatakuliah/<matkul_id>', methods=['GET', 'POST'])
def edit_matakuliah(matkul_id):
    obj_id = ObjectId(matkul_id)

    if request.method == 'GET':
        document = collection1.find_one({'_id': obj_id})

        if document:
            return render_template('editMatakuliah.html', document=document)
        else:
            return 'Data tidak ditemukan'

    elif request.method == 'POST':
        kodeMatakuliah = request.form['kodeMatakuliah']
        namaMatakuliah = request.form['namaMatakuliah']
        hariMasuk = request.form['hariMasuk']
        jamMasuk = request.form['jamMasuk']
        jamKeluar = request.form['jamKeluar']

        result = collection1.update_one(
            {'_id': obj_id},
            {
                '$set': {
                    'kode_matakuliah': kodeMatakuliah,
                    'nama_matakuliah': namaMatakuliah,
                    'hari': hariMasuk,
                    'jam_masuk': jamMasuk,
                    'jam_keluar': jamKeluar
                }
            }
        )

        if result.modified_count > 0:
            return redirect(url_for('tableMatkul'))
        else:
            return 'Data tidak ditemukan'

@app.route('/addMatakuliah', methods=['POST'])
def add_matkul_matakuliah():
    kodeMatakuliah = request.form['kodeMatakuliah']
    namaMatakuliah = request.form['namaMatakuliah']
    hariMasuk = request.form['hariMasuk']
    jamMasuk = request.form['jamMasuk']
    jamKeluar = request.form['jamKeluar']

    document = {
        'kode_matakuliah': kodeMatakuliah,
        'nama_matakuliah': namaMatakuliah,
        'hari': hariMasuk,
        'jam_masuk': jamMasuk,
        'jam_keluar': jamKeluar
    }

    result = collection1.insert_one(document)

    if result.inserted_id:
        return redirect(url_for('tableMatkul'))
    else:
        return 'Gagal menambahkan data'

@app.route('/charts')
def charts():
    # Render the charts.html template
    return render_template('charts.html')

@app.route('/login')
def login():
    # Render the login.html template
    return render_template('login.html')

@app.route('/register')
def register():
    # Render the register.html template
    return render_template('register.html')

@app.route('/tampilkanMatkul')
def table_matkul():
    # Get all documents from the matkul collection
    documents = collection2.find()

    # If there are no documents, return an empty list
    if not documents:
        return render_template('tabelMatkul.html', tableData=None)

    # Create a list to store the table data
    tableData = []

    # Iterate through the documents and add the data to the list
    for document in documents:
        tableData.append({
            "_id": str(document['_id']),
            "matakuliah": document['matakuliah'],
            "pembagian": document['pembagian']
        })

    # Return the table data to the template
    return render_template('tabelMatkul.html', tableData=tableData)

@app.route('/hapusMatkul/<matkul_id>', methods=['GET', 'POST'])
def delete_matkul(matkul_id):
    obj_id = ObjectId(matkul_id)

    result = collection2.delete_one({'_id': obj_id})

    if result.deleted_count > 0:
        return redirect(url_for('table_matkul'))
    else:
        return 'Data tidak ditemukan'

@app.route('/ubahMatkul/<matkul_id>', methods=['GET', 'POST'])
def edit_matkul(matkul_id):
    obj_id = ObjectId(matkul_id)

    if request.method == 'GET':
        document = collection2.find_one({'_id': obj_id})

        if document:
            return render_template('editMatkul.html', document=document)
        else:
            return 'Data tidak ditemukan'

    elif request.method == 'POST':
        # Retrieve the existing document
        existing_document = collection2.find_one({'_id': obj_id})

        # Create a new dictionary for the updated document
        updated_document = existing_document.copy()

        # Update the 'matakuliah' field
        updated_document['matakuliah'] = request.form['matakuliah']

        # Update the 'pembagian' field
        for pembagian in updated_document['pembagian']:
            pembagian['kelas'] = request.form.get('kelas')
            pembagian['hari'] = request.form.get('hari')
            pembagian['jamMasuk'] = request.form.get('jamMasuk')
            pembagian['jamPulang'] = request.form.get('jamPulang')

        # Save the updated document back to the database
        result = collection2.replace_one({'_id': obj_id}, updated_document)

        if result.modified_count > 0:
            return redirect(url_for('table_matkul'))
        else:
            return 'Data tidak ditemukan'

@app.route('/tambahMatkul', methods=['POST'])
def add_matkul():
    matakuliah = request.form['matakuliah']
    kelas = request.form['kelas']
    hari = request.form['hari']
    jamMasuk = request.form['jamMasuk']
    jamPulang = request.form['jamPulang']

    document = {
        'matakuliah': matakuliah,
        'pembagian': [{'kelas': kelas, 'hari': hari, 'jamMasuk': jamMasuk, 'jamPulang': jamPulang}]
    }

    result = collection2.insert_one(document)

    if result.inserted_id:
        return redirect(url_for('table_matkul'))
    else:
        return 'Gagal menambahkan data'

@app.route('/tampilkanMahasiswa')
def table_mahasiswa():
    # Get all documents from the mahasiswa collection
    documents = collection3.find()

    # If there are no documents, return an empty list
    if not documents:
        return render_template('tabelMahasiswa.html', tableData=None)

    # Create a list to store the table data
    tableData = []

    # Iterate through the documents and add the data to the list
    for document in documents:
        tableData.append({
            "_id": str(document['_id']),
            "nama_lengkap": document['nama_lengkap'],
            "nim": document['nim'],
            "kelas": document['kelas']
        })

    # Return the table data to the template
    return render_template('tabelMahasiswa.html', tableData=tableData)

@app.route('/hapusMahasiswa/<mahasiswa_id>', methods=['GET', 'POST'])
def delete_mahasiswa(mahasiswa_id):
    obj_id = ObjectId(mahasiswa_id)

    result = collection3.delete_one({'_id': obj_id})

    if result.deleted_count > 0:
        return redirect(url_for('table_mahasiswa'))
    else:
        return 'Data tidak ditemukan'

@app.route('/ubahMahasiswa/<mahasiswa_id>', methods=['GET', 'POST'])
def edit_mahasiswa(mahasiswa_id):
    obj_id = ObjectId(mahasiswa_id)

    if request.method == 'GET':
        document = collection3.find_one({'_id': obj_id})

        if document:
            return render_template('editMahasiswa.html', document=document)
        else:
            return 'Data tidak ditemukan'

    elif request.method == 'POST':
        # Retrieve the existing document
        existing_document = collection3.find_one({'_id': obj_id})

        # Create a new dictionary for the updated document
        updated_document = existing_document.copy()

        # Update the 'nama_lengkap' field
        updated_document['nama_lengkap'] = request.form['nama_lengkap']

        # Update the 'nim' field
        updated_document['nim'] = request.form['nim']

        # Update the 'kelas' field
        updated_document['kelas'] = request.form['kelas']

        # Save the updated document back to the database
        result = collection3.replace_one({'_id': obj_id}, updated_document)

        if result.modified_count > 0:
            return redirect(url_for('table_mahasiswa'))
        else:
            return 'Data tidak ditemukan'

@app.route('/tambahMahasiswa', methods=['POST'])
def add_mahasiswa():
    nama_lengkap = request.form['nama_lengkap']
    nim = request.form['nim']
    kelas = request.form['kelas']

    document = {
        'nama_lengkap': nama_lengkap,
        'nim': nim,
        'kelas': kelas
    }

    result = collection3.insert_one(document)

    if result.inserted_id:
        return redirect(url_for('table_mahasiswa'))
    else:
        return 'Gagal menambahkan data'

@app.route('/tampilkanLogAbsen')
def table_logabsen():
    # Get all documents from the collection4 (assuming it's the logabsen collection)
    documents = collection4.find()

    # If there are no documents, return an empty list
    if not documents:
        return render_template('tabelLogabsen.html', tableData=None)

    # Create a list to store the table data
    tableData = []

    # Iterate through the documents and add the data to the list
    for document in documents:
        tableData.append({
            "_id": str(document['_id']),
            "nama_lengkap": str(document["nama_lengkap"]),
            "nim": str(document["nim"]),
            "kelas": str(document["kelas"]),
            "matkul": str(document["matkul"]),
            "hari": str(document["hari"]),
            "tanggal": str(document["tanggal"]),
            "jam": str(document["jam"]),
            "status": str(document["status"])
        })

    # Return the table data to the template
    return render_template('tabelLogabsen.html', tableData=tableData)

@app.route('/hapusLogAbsen/<logabsen_id>', methods=['GET', 'POST'])
def delete_logabsen(logabsen_id):
    obj_id = ObjectId(logabsen_id)

    result = collection4.delete_one({'_id': obj_id})

    if result.deleted_count > 0:
        return redirect(url_for('table_logabsen'))
    else:
        return 'Data tidak ditemukan'

@app.route('/ubahLogAbsen/<logabsen_id>', methods=['GET', 'POST'])
def edit_logabsen(logabsen_id):
    obj_id = ObjectId(logabsen_id)

    if request.method == 'GET':
        document = collection4.find_one({'_id': obj_id})

        if document:
            return render_template('editLogAbsen.html', document=document)
        else:
            return 'Data tidak ditemukan'

    elif request.method == 'POST':
        # Retrieve the existing document
        existing_document = collection4.find_one({'_id': obj_id})

        # Create a new dictionary for the updated document
        updated_document = existing_document.copy()

        # Update the fields based on your form inputs
        updated_document['nama'] = request.form['nama']
        updated_document['nim'] = request.form['nim']
        updated_document['kelas'] = request.form['kelas']
        updated_document['tanggal'] = request.form['tanggal']
        updated_document['foto'] = request.form['foto']
        updated_document['jamMasuk'] = request.form['jamMasuk']
        updated_document['jamPulang'] = request.form['jamPulang']

        # Save the updated document back to the database
        result = collection4.replace_one({'_id': obj_id}, updated_document)

        if result.modified_count > 0:
            return redirect(url_for('table_logabsen'))
        else:
            return 'Data tidak ditemukan'

@app.route('/tambahLogAbsen', methods=['POST'])
def add_logabsen():
    nama = request.form['nama']
    nim = request.form['nim']
    kelas = request.form['kelas']
    tanggal = request.form['tanggal']
    foto = request.form['foto']
    jamMasuk = request.form['jamMasuk']
    jamPulang = request.form['jamPulang']

    document = {
        'nama': nama,
        'nim': nim,
        'kelas': kelas,
        'tanggal': tanggal,
        'foto': foto,
        'jamMasuk': jamMasuk,
        'jamPulang': jamPulang
    }

    result = collection4.insert_one(document)

    if result.inserted_id:
        return redirect(url_for('table_logabsen'))
    else:
        return 'Gagal menambahkan data'

@app.route('/tampilkanCatatanAbsen/<string:mahasiswa_id>', methods=['GET'])
def tampilkan_catatan_absen(mahasiswa_id):
    # Dapatkan dokumen Mahasiswa berdasarkan ID yang diberikan
    mahasiswa = collection3.find_one({'_id': ObjectId(mahasiswa_id)})

    if not mahasiswa:
        return "Mahasiswa not found"

    # Dapatkan data Log Absen untuk Mahasiswa berdasarkan nim
    logabsen_data = collection4.find({'nim': mahasiswa['nim']})

    # Buat daftar untuk menyimpan data tabel Log Absen
    logabsen_table_data = []

    # Iterasi melalui data Log Absen dan tambahkan ke daftar
    for logabsen in logabsen_data:
        logabsen_table_data.append({
            "_id": str(logabsen['_id']),
            "tanggal": logabsen['tanggal'],
            "jamMasuk": logabsen['jamMasuk'],
            "jamPulang": logabsen['jamPulang']
        })

    # Render template dengan data Mahasiswa dan data tabel Log Absen
    return render_template('tabelMahasiswa.html', mahasiswa=mahasiswa, absen=logabsen_table_data)

def create_training_folder(folder_name):
    folder_path = os.path.join("training", folder_name)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder '{folder_name}' created successfully in the 'training' directory.")
    else:
        print(f"Folder '{folder_name}' already exists in the 'training' directory.")

def capture_images(folder_name, num_images=10, camera_url=""):
    folder_path = os.path.join("training", folder_name)

    if os.path.exists(folder_path):
        print("Starting image capture. Please align your face straight towards the camera.")

        if not camera_url:
            camera_url = request.form['camera_url']

        count = 0
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        while count < num_images:
            stream = urllib.request.urlopen(camera_url)
            byte_data = bytes()

            while True:
                data = stream.read(1024)
                if not data:
                    break

                byte_data += data
                a = byte_data.find(b"\xff\xd8")
                b = byte_data.find(b"\xff\xd9")

                if a != -1 and b != -1:
                    jpg = byte_data[a:b + 2]
                    byte_data = byte_data[b + 2:]

                    frame = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    flipped_frame = cv2.flip(frame, -1)
                    gray_frame = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

                    for (x, y, w, h) in faces:
                        cv2.rectangle(flipped_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        face_image = flipped_frame

                        time.sleep(1)
                        image_path = os.path.join(folder_path, f"{count + 1}.png")
                        cv2.imwrite(image_path, face_image)

                        print(f"Image {count + 1}/{num_images} captured.")

                        count += 1

                        if count == num_images:
                            break

                    if count == num_images:
                        break

        print("Image capture completed.")
    else:
        print(f"Folder '{folder_name}' does not exist in the 'training' directory.")
  
def create_validation_folder():
    if not os.path.exists("validation"):
        os.makedirs("validation")
        print("Validation folder created successfully.")
    else:
        print("Validation folder already exists.")

def capture_and_validate(url):
    capture_stream = cv2.VideoCapture(url)
    faces_detected = False
    start_time = 0
    validate_process = None

    while True:
        ret, frame = capture_stream.read()

        if not ret:
            # Reconnect stream if connection is lost
            capture_stream = cv2.VideoCapture(url)
            continue

        # Rotate frame 180 degrees
        rotated_frame = cv2.rotate(frame, cv2.ROTATE_180)

        gray = cv2.cvtColor(rotated_frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            # Wajah terdeteksi, perbarui waktu mulai jika belum ada wajah sebelumnya
            if not faces_detected:
                start_time = time.time()
            faces_detected = True

            # Gambar kotak pembatas (bounding box) di sekitar wajah
            for (x, y, w, h) in faces:
                cv2.rectangle(rotated_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Cek apakah wajah terdeteksi selama 3 detik sebelum mengambil gambar
            current_time = time.time()
            if current_time - start_time >= 3:
                # Simpan frame yang memiliki wajah terdeteksi
                timestamp = int(time.time())
                image_name = f"{validation_folder}/camera_frame_{timestamp}.jpg"
                cv2.imwrite(image_name, rotated_frame)
                faces_detected = False

                # Jalankan program validateRev4.py
                if validate_process is None or validate_process.poll() is not None:
                    validate_process = subprocess.Popen(["python3", "validateRev4.py"])

        cv2.imshow("Camera", rotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000, debug=True)

