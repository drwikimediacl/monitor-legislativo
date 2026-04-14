import pandas as pd

URL = "https://docs.google.com/spreadsheets/d/1RBS_VB7d3jyJvJL87gBZg5hx8I2PKslBfd3kWAxVdgA/export?format=csv"

OUTPUT = "data/watchlist_enriched.xlsx"

def main():
    df = pd.read_csv(URL)

    df.columns = [c.strip().lower() for c in df.columns]

    df = df.dropna(subset=["boletin", "url"])
    df["boletin"] = df["boletin"].astype(str).str.strip()

    df.to_excel(OUTPUT, index=False)

    print(f"Watchlist lista: {len(df)} proyectos")

if __name__ == "__main__":
    main()
