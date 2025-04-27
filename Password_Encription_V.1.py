import json
import os
from cryptography.fernet import Fernet
import hashlib
import base64
from getpass import getpass

DB_FILE = 'passwords.json'

def derive_key(master_password):
    # Derive a 32-byte key from the master password
    digest = hashlib.sha256(master_password.encode()).digest()
    return base64.urlsafe_b64encode(digest)

def load_passwords():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_passwords(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f)

def add_password(master_password):
    site = input("Enter site name: ")
    password = getpass("Enter password for the site: ")

    key = derive_key(master_password)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(password.encode())

    passwords = load_passwords()
    passwords[site] = encrypted.decode()
    save_passwords(passwords)
    print(f"Password for {site} saved successfully.")

def view_sites():
    passwords = load_passwords()
    if not passwords:
        print("No passwords saved.")
        return
    print("Saved sites:")
    for site in passwords.keys():
        print(f"- {site}")

def get_password(master_password):
    site = input("Enter the site you want the password for: ")
    passwords = load_passwords()
    if site not in passwords:
        print("Site not found.")
        return
    key = derive_key(master_password)
    fernet = Fernet(key)
    try:
        decrypted = fernet.decrypt(passwords[site].encode()).decode()
        print(f"Password for {site}: {decrypted}")
    except Exception:
        print("Incorrect master password!")

def main():
    print("=== Password Manager ===")
    while True:
        print("\nOptions:")
        print("1. Add new password")
        print("2. View saved sites")
        print("3. Get password for site")
        print("4. Exit")
        choice = input("Choose an option: ")

        if choice == '1':
            master = getpass("Enter master password: ")
            add_password(master)
        elif choice == '2':
            view_sites()
        elif choice == '3':
            master = getpass("Enter master password: ")
            get_password(master)
        elif choice == '4':
            break
        else:
            print("Invalid option.")

if __name__ == '__main__':
    main()
