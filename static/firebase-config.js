import { initializeApp } from "https://www.gstatic.com/firebasejs/10.9.0/firebase-app.js";
import { GoogleAuthProvider } from "https://www.gstatic.com/firebasejs/10.9.0/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.9.0/firebase-firestore.js";


import { getAuth } from "https://www.gstatic.com/firebasejs/10.9.0/firebase-auth.js";


// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyDiBobZPYnnwg8uTcuQUm_CXR6VdHW87Xw",
  authDomain: "tfm-project-52a8d.firebaseapp.com",
  projectId: "tfm-project-52a8d",
  storageBucket: "tfm-project-52a8d.firebasestorage.app",
  messagingSenderId: "653105265121",
  appId: "1:653105265121:web:a192945a08b0fe85e6faa0",
  measurementId: "G-WTYWVL4N5G"
};

  // Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();

const db = getFirestore(app);

export { auth, provider, db };

