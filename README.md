# 🎧 YT Audio

Personal music searching and streaming app.

**Features** search and play from Bandcamp, YouTube or URL.

**Needs** and a play queue.

![Demo](docs/yt-audio.gif)


## Installation

YT Audio uses an API wrapped around [`yt-dlp`](https://github.com/yt-dlp/yt-dlp). You need to run the server-side API before you can use the front-end UI in the browser.

1. **Clone** the code

    ```sh
    git clone https://github.com/damiencorpataux/yt-dlp-audio-api.git
    cd yt-dlp-audio-api
    ```

2. **Run the API** (in Docker or baremetal on your system)

    - in **Docker**
        ```sh
        docker compose up --build
        ```

    - or **baremetal** on your system
        ```sh
        pip install -r requirements
        cd yt-audio
        uvicorn app:app --host 0.0.0.0 --reload
        ```

3. **Search & play music** at http://localhost:8000

    Visit http://localhost:8000 if you installed YT Audio on your local computer
    or use the IP/hostname of the server you installed it on.

    ⚠️ Be careful to **not expose the API to the public**
    because requests to music providers (Bandcamp, YouTube) are made from your IP address.


## Documentation

API Routes: http://localhost:8000/docs