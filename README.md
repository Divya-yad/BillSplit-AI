# 🧾 BillSplit AI

> **Turn restaurant bill photos into verified, paisa-exact, per-person cost breakdowns.**  
> Powered by Google Gemini Vision, deterministic proportional mathematics, and an interactive React interface.

---

## 🌟 Overview

Splitting restaurant bills with groups often leads to unfair math:
- Tax, service charges, and discounts are typically split equally by headcount, penalizing light eaters or non-drinkers.
- People who order an expensive item or beverage end up subsidized by friends.
- Someone who left early gets unfairly charged for dessert or after-dinner rounds.
- Minor rounding discrepancies lead to totals that don't match the printed receipt.

**BillSplit AI** solves these challenges end-to-end:
1. **Multimodal AI Vision**: Analyzes 1–3 receipt photos using Google Gemini models with automated OpenCV preprocessing.
2. **Deterministic Server Math**: Never trusts LLM arithmetic—all subtotals, taxes, and discounts are computed server-side with Python's high-precision `Decimal`.
3. **Proportional Fairness Engine**: Allocates taxes, service fees, discounts, and tips strictly proportional to consumption, not headcount.
4. **Early-Leaver Protection**: Accurately handles participants who left before specific charges or rounds.
5. **Exact Paisa/Cent Rounding**: Employs the largest-remainder method (Hamilton-Hare method) to guarantee that the sum of all individual shares matches the authoritative receipt total to the exact paisa.
6. **Confidence Review & Export**: Flags low-confidence extractions for quick user adjustments and exports downloadable summary cards.

---

## 📐 System Architecture

```
                               ┌────────────────────────┐
                               │  Receipt Photo Upload  │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │  OpenCV Preprocessing  │
                               │  (Contrast, Threshold) │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │  Google Gemini Vision  │
                               │  (Structured JSON OCR) │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │ Server-Side Validation │
                               │  & Sanity Verification │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │  Interactive UI Review │
                               │  & People Assignments  │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │ Proportional Split     │
                               │ Engine (Exact Paisa)   │
                               └────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **AI / Vision**: [Google GenAI SDK](https://github.com/google/generative-ai-python) (`google-genai`) with Gemini models (fallback support for `gemini-flash-latest`, `gemini-3.5-flash`, etc.)
- **Image Processing**: OpenCV (`opencv-python-headless`) & Pillow (`PIL`)
- **Data Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Database & ORM**: SQLite via [SQLAlchemy 2.0 (Async)](https://docs.sqlalchemy.org/) & `aiosqlite`
- **Testing**: Pytest & `pytest-asyncio`

### Frontend
- **Framework**: [React 18](https://react.dev/) + [Vite](https://vitejs.dev/)
- **State Management**: [Zustand](https://github.com/pmndrs/zustand)
- **HTTP Client**: [Axios](https://axios-http.com/)
- **Export Utility**: [html2canvas](https://html2canvas.hertzen.com/) (downloadable receipt breakdown cards)
- **Styling**: Modern Vanilla CSS Design System with dark theme and micro-interactions

---

## 📁 Repository Structure

```
.
├── .gitignore
├── README.md
├── backend/
│   ├── engine/
│   │   ├── assign.py            # Assignment resolution helpers
│   │   └── split.py             # Deterministic proportional split engine
│   ├── eval/
│   │   └── run_eval.py          # Vision extraction benchmarks & evaluation
│   ├── models/
│   │   └── schemas.py           # Pydantic schemas (ExtractedBill, Breakdown, etc.)
│   ├── routes/
│   │   └── bills.py             # FastAPI REST endpoints (/bills/*)
│   ├── storage/
│   │   └── db.py                # Async SQLite SQLAlchemy session & model
│   ├── tests/
│   │   └── test_split_engine.py # Comprehensive test suite for split logic
│   ├── vision/
│   │   ├── extract.py           # Gemini API structured extraction & fallbacks
│   │   └── preprocess.py        # Image contrast, rotation, and cleaning
│   ├── .env.example             # Template for environment variables
│   ├── main.py                  # FastAPI application entry point
│   └── requirements.txt         # Python dependencies
└── frontend/
    ├── public/
    ├── src/
    │   ├── api/
    │   │   └── client.js        # Axios API client functions
    │   ├── components/
    │   │   ├── UploadScreen.jsx    # Photo upload & camera capture
    │   │   ├── ReviewScreen.jsx    # Item verification & confidence tags
    │   │   ├── PeopleScreen.jsx    # Group members & early-leaver toggles
    │   │   ├── AssignScreen.jsx    # Tap/drag line item allocation & shares
    │   │   └── BreakdownScreen.jsx # Final split breakdown & receipt export
    │   ├── store/
    │   │   └── billStore.js     # Zustand state store
    │   ├── App.jsx              # Main view & step progress bar
    │   ├── index.css            # Design tokens, variables, and animations
    │   └── main.jsx             # React entry point
    ├── index.html
    ├── package.json
    └── vite.config.js           # Vite dev server & backend proxy configuration
```

---

## 🚀 Getting Started

### Prerequisites
- **Python**: 3.10 or higher
- **Node.js**: 18.x or higher (with `npm`)
- **Google Gemini API Key**: [Get an API Key from Google AI Studio](https://aistudio.google.com/)

---

### 1. Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   - **On Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **On macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file by copying `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and supply your Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key
   GEMINI_MODEL=gemini-flash-latest
   GEMINI_FALLBACK_MODEL=gemini-3.5-flash
   DATABASE_URL=sqlite+aiosqlite:///./billsplit.db
   ENVIRONMENT=development
   ```

5. **Start the backend server**:
   ```bash
   python main.py
   # or
   uvicorn main:app --reload --port 8000
   ```
   The backend will start at `http://localhost:8000`.  
   Interactive Swagger docs are accessible at `http://localhost:8000/docs`.

---

### 2. Frontend Setup

1. **Navigate to the frontend directory** (in a separate terminal):
   ```bash
   cd frontend
   ```

2. **Install npm dependencies**:
   ```bash
   npm install
   ```

3. **Start the Vite development server**:
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`.  
   Requests to `/bills` and `/health` are automatically proxied to `http://localhost:8000`.

---

## 🧪 Running Tests

Verify the core split calculation engine and rounding invariant checks:

```bash
cd backend
pytest -v
```

This verifies:
- Paisa-exact matching (`sum(shares) == authoritative_total`)
- Proportional taxes and discounts
- Single-item consumer math (e.g. Coke-only participant pays only Coke tax)
- Rounding adjustments using the largest-remainder method
- Early-departure exclusions

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/bills/upload` | Upload 1–3 bill images; runs preprocessing, Gemini OCR extraction, and creates a bill session. |
| `GET` | `/bills/{bill_id}` | Retrieve complete bill state (extracted items, participants, assignments, breakdown). |
| `PATCH`| `/bills/{bill_id}/correct` | Apply user corrections to items, quantities, or taxes with server-side recalculation. |
| `POST` | `/bills/{bill_id}/people` | Save participant list with optional `left_early` status. |
| `POST` | `/bills/{bill_id}/assign` | Save item-to-person assignments and fractional shares. |
| `GET` | `/bills/{bill_id}/compute` | Run the split engine and return the per-person breakdown. |
| `GET` | `/health` | Service health check. |

---

## 🧮 Mathematical Split Engine

### Proportional Charges
Rather than splitting taxes ($T$) or service charges ($S$) equally across $N$ people:
$$\text{Tax Share}_i = T \times \left( \frac{\text{Subtotal}_i}{\text{Total Subtotal}} \right)$$
A person who ordered ₹200 worth of food pays half the tax of someone who ordered ₹400 worth.

### Largest-Remainder Rounding (Hamilton-Hare)
When splitting cents or paise, dividing fractions produces rounding remainders:
$$R = \text{Authoritative Total} - \sum_{i=1}^N \lfloor \text{Person Total}_i \rfloor$$
The leftover pennies/paise are distributed one-by-one to individuals with the highest fractional remainder until the exact sum matches the bill.

---

## 📄 License

This project is licensed under the MIT License.
