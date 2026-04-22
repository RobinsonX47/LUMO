from lumo.core.app import app, create_app, Config

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("LUMO Movie Platform Starting...")
    print("=" * 60)
    print(f"? Database: {Config.SQLALCHEMY_DATABASE_URI}")
    print(f"? TMDB API: {'Configured' if Config.TMDB_API_KEY != 'YOUR_TMDB_API_KEY_HERE' else '?? NOT CONFIGURED'}")
    print("?? Running on: http://localhost:5000")
    print("=" * 60 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
