💊 Medicine Dataset Outputs 

This folder contains cleaned and preprocessed medicine dataset files prepared by Member 1 – Data Collection, Cleaning & Preprocessing for the Personalized Healthcare Recommendation System.

📂 Available Files 1. medicine_tfidf_matrix.npz Contains the TF-IDF numerical representation of medicine-related text. Stores sparse matrix data to reduce storage requirements. Used for text similarity calculations. Can be loaded using SciPy. 2. medicine_tfidf_vectorizer.joblib Contains the fitted TF-IDF vectorizer. Converts medicine descriptions and related text into numerical feature vectors. Must be reused for consistent text transformation. 3. medicine_data_metadata.json Stores dataset metadata and preprocessing information. Contains information about detected medicine columns and text preparation. Helps developers understand the dataset structure. 📁 Folder Structure medicine_outputs/ │ ├── medicine_tfidf_matrix.npz ├── medicine_tfidf_vectorizer.joblib ├── medicine_data_metadata.json └── README.md 👥 Module Responsibility 

Member 1 – Data Preparation

Medicine dataset inspection and cleaning. Missing-value and duplicate checks. Text preprocessing. TF-IDF vectorization. Exporting prepared medicine data and supporting files. 

Member 3 – Medicine Recommendation

Developing the medicine recommendation engine. Implementing cosine similarity. Integrating TF-IDF features. Building the recommendation workflow. Testing and validating recommendation outputs. ⚙️ Instructions for Member 3 Read medicine_data_metadata.json before integration. Load the fitted vectorizer using Joblib. Load the TF-IDF matrix using SciPy. Confirm that the matrix row order matches the corresponding medicine records in cleaned_medicine_prepared.csv. Use the same fitted vectorizer for new text inputs. Validate recommendation results before integration. 🧪 Loading Files in Python import joblib from scipy.sparse import load_npz # Load fitted TF-IDF vectorizer vectorizer = joblib.load( "medicine_tfidf_vectorizer.joblib" ) # Load TF-IDF matrix tfidf_matrix = load_npz( "medicine_tfidf_matrix.npz" ) print("Vectorizer loaded successfully") print("Matrix shape:", tfidf_matrix.shape) ⚠️ Important Notes These files support text similarity and recommendation development. Similarity scores do not establish medicine equivalence or clinical suitability. Recommendations must not be treated as prescriptions. Qualified healthcare professional review is required before real-world use. Check dataset licensing before redistribution. 

Project: Personalized Healthcare Recommendation System
Module: Medicine Dataset Preparation
Prepared by: Member 1
For Integration: Member 3
