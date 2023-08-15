from flask import Flask, request, jsonify
from flask_restful import Resource, Api
import pandas as pd
import pickle
from sklearn.base import BaseEstimator, TransformerMixin
import tensorflow as tf
import keras


app = Flask(__name__)
api = Api(app)

with open("train_model/users/preprocessing_pipeline.pkl", "rb") as f:
    preprocessing_pipeline = pickle.load(f)

model = tf.keras.models.load_model("train_model/users/user_model.keras")
class LengthTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, columns):
        self.columns = columns

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X_copy = X.copy()
        for col in self.columns:
            X_copy[col + "_length"] = X_copy[col].apply(
                lambda x: len(str(x)) if pd.notnull(x) else 0
            )
        return X_copy


class IsNullTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, columns):
        self.columns = columns

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X_copy = X.copy()
        for col in self.columns:
            X_copy[col + "_isnull"] = X_copy[col].isnull().astype(int)
        return X_copy


class UserSpamClassifier(Resource):
    def post(self):
        data = request.get_json(force=True)

        df = pd.DataFrame([data])

        numeric_features = [
            "theme_id",
            "color_scheme_id",
            "projects_limit",
            "namespace_id",
        ]
        categorical_features = [
            "bot",
            "last_sign_in_at",
            "confirmed_at",
            "last_activity_on",
            "current_sign_in_at",
            "can_create_group",
            "can_create_project",
            "two_factor_enabled",
            "external",
            "private_profile",
            "is_admin",
            "note",
        ]
        text_features = [
            "username",
            "name",
            "bio",
            "location",
            "website_url",
            "public_email",
            "organization",
            "skype",
            "linkedin",
            "twitter",
            "job_title",
            "pronouns",
            "work_information",
            "email",
            "commit_email",
            "avatar_url",
        ]

        length_transformer = LengthTransformer(text_features)
        df = length_transformer.transform(df)

        is_null_transformer = IsNullTransformer(text_features)
        df = is_null_transformer.transform(df)

        df["combined_text"] = df[text_features].apply(
            lambda row: " ".join(row.values.astype(str)), axis=1
        )
        text_features = ["combined_text"]

        processed_data = preprocessing_pipeline.transform(df)

        prediction = model.predict(processed_data)

        prediction_label = 1 if prediction > 0.5 else 0

        return jsonify({"prediction": prediction_label, "score": prediction.item()})


api.add_resource(UserSpamClassifier, "/predict_user_create")

if __name__ == "__main__":
    app.run(port=5000, debug=True)
