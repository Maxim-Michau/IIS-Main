"""Machine-learning categoriser."""

from pathlib import Path
from typing import Sequence
import warnings
import joblib
from scipy import sparse
from scipy.optimize import OptimizeWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion
from sklearn.calibration import CalibratedClassifierCV
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.ai.categorisers.base import Categoriser
from config.settings import MODEL_PATH

warnings.filterwarnings(
    "ignore",
    message=r"Unknown solver options: iprint",
    category=OptimizeWarning,
)


class MLCategoriser(Categoriser):
    """Calibrated TF-IDF and amount/hour logistic categoriser."""

    def __init__(self, model_path: str | Path = MODEL_PATH) -> None:
        """Load a persisted model if available."""
        self.model_path = Path(model_path)
        self.model = joblib.load(self.model_path) if self.model_path.exists() else None

    def is_trained(self) -> bool:
        """Return whether a persisted or in-memory model is available."""
        return self.model is not None

    def train(self, merchants: Sequence[str], categories: Sequence[str],
              amounts: Sequence[float], hours: Sequence[int]) -> None:
        """Train a calibrated probabilistic classifier."""
        if len(set(categories)) < 2 or len(categories) < 10:
            raise ValueError("At least 10 labelled rows and 2 categories are required")
        text_vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4))
        word_vectorizer = TfidfVectorizer(analyzer="word")
        features = FeatureUnion([("char", text_vectorizer), ("word", word_vectorizer)])
        merchant_features = features.fit_transform(merchants)
        numeric = sparse.csr_matrix([
            [self._amount_band(amount), hour / 24.0] for amount, hour in zip(amounts, hours)
        ])
        base = LogisticRegression(max_iter=300, class_weight="balanced")
        counts = {category: list(categories).count(category) for category in set(categories)}
        cv = min(3, min(counts.values()))
        if cv < 2:
            raise ValueError("Each category needs at least 2 training examples")
        classifier = CalibratedClassifierCV(base, method="sigmoid", cv=cv)
        classifier.fit(sparse.hstack([merchant_features, numeric]), categories)
        self.model = (features, classifier)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.model_path)

    def categorise(self, transaction: Transaction) -> Prediction:
        """Return calibrated class probability or a low-confidence fallback."""
        if self.model is None:
            return Prediction("Other", 0.25, "No trained model is available yet.", "ML")
        features, classifier = self.model
        merchant_features = features.transform([transaction.merchant_clean or transaction.merchant_raw])
        numeric = sparse.csr_matrix([[
            self._amount_band(transaction.amount),
            transaction.timestamp.hour / 24.0,
        ]])
        probabilities = classifier.predict_proba(sparse.hstack([merchant_features, numeric]))[0]
        index = int(probabilities.argmax())
        category = str(classifier.classes_[index])
        confidence = float(probabilities[index])
        matched = self._top_tokens(features, classifier, category, transaction.merchant_clean)
        detail = f"Matched on: {', '.join(repr(token) for token in matched)}" if matched else (
            f"Similar to merchants labelled {category}"
        )
        return Prediction(category, confidence,
                          f"{detail}.", "ML")

    @staticmethod
    def _top_tokens(features: FeatureUnion, classifier: object, category: str,
                     merchant: str) -> list[str]:
        """Return matching merchant tokens with high classifier weight."""
        word_vectorizer = dict(features.transformer_list).get("word")
        if word_vectorizer is None:
            return []
        try:
            class_index = list(classifier.classes_).index(category)
            calibrated = getattr(classifier, "calibrated_classifiers_", [])
            estimator = calibrated[0].estimator if calibrated else classifier
            coefficients = estimator.coef_
            if coefficients.ndim == 1:
                weights = coefficients
            else:
                weights = coefficients[class_index if class_index < len(coefficients) else 0]
        except (AttributeError, ValueError, IndexError):
            return []
        vocabulary = word_vectorizer.vocabulary_
        merchant_tokens = {token for token in merchant.lower().replace("/", " ").split()}
        ranked = sorted(
            ((weights[index], token) for token, index in vocabulary.items()
             if token in merchant_tokens),
            reverse=True,
        )
        return [token for _, token in ranked[:3]]

    @staticmethod
    def _amount_band(amount: float) -> float:
        """Convert amount into a stable normalised band."""
        if amount < 10:
            return 0.0
        if amount < 30:
            return 0.5
        return 1.0
