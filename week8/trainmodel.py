# mlops_assignment/
# ├── data/
# │   ├── train.csv
# │   ├── test.csv
# ├── src/
# │   ├── train_model.py
# │   ├── evaluate_model.py
# │   ├── drift_check.py
# ├── .github/
# │   └── workflows/
# │       └── ci.yml
# ├── requirements.txt
# └── README.md


import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from mlflow.models.signature import infer_signature

# Set MLflow experiment
mlflow.set_experiment("iris_rf_experiment")

# Load dataset
data = load_iris()

X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

# Start MLflow run
with mlflow.start_run():

    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)

    # Log parameters
    mlflow.log_params({
        "n_estimators": 50,
        "random_state": 42
    })

    # Log metric
    mlflow.log_metric("accuracy", acc)

    # Log model with signature
    signature = infer_signature(X_train, preds)
    mlflow.sklearn.log_model(model, "model", signature=signature)

    print("Logged accuracy:", acc)