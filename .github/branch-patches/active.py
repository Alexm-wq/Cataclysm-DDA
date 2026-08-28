from pathlib import Path

path = Path("src/sdltiles.cpp")
text = path.read_text(encoding="utf-8")

anchor = "static ui_pixel_button_debug_stats ui_pixel_button_debug;\n\n"
if text.count(anchor) != 1:
    raise SystemExit("pixel HUD debug stats anchor missing or duplicated")

helper = r'''static ui_pixel_button_debug_stats ui_pixel_button_debug;

static std::ofstream &pixel_hud_debug_stream()
{
    static std::ofstream stream;
    static bool initialized = false;
    if( !initialized ) {
        initialized = true;
        std::string directory = PATH_INFO::config_dir();
        if( !directory.empty() && directory.back() != '/' && directory.back() != '\\' ) {
            directory.push_back( '/' );
        }
        stream.open( directory + "pixel_hud_debug.log", std::ios::out | std::ios::trunc );
        if( !stream ) {
            stream.clear();
            stream.open( "pixel_hud_debug.log", std::ios::out | std::ios::trunc );
        }
        if( stream ) {
            stream << "pixel HUD diagnostics started" << '\n';
            stream.flush();
        }
    }
    return stream;
}

class pixel_hud_log_line
{
    public:
        pixel_hud_log_line() : stream_( pixel_hud_debug_stream() ) {
            if( stream_ ) {
                stream_ << SDL_GetTicks() << ' ';
            }
        }

        ~pixel_hud_log_line() {
            if( stream_ ) {
                stream_ << '\n';
                stream_.flush();
            }
        }

        template<typename T>
        pixel_hud_log_line &operator<<( const T &value ) {
            if( stream_ ) {
                stream_ << value;
            }
            return *this;
        }

    private:
        std::ofstream &stream_;
};

static pixel_hud_log_line pixel_hud_log()
{
    return pixel_hud_log_line();
}

'''
text = text.replace(anchor, helper, 1)

needle = 'dbg( D_INFO ) << "[pixel-hud]'
count = text.count(needle)
if count < 4:
    raise SystemExit(f"expected several SDL pixel HUD info logs, found {count}")
text = text.replace(needle, 'pixel_hud_log() << "[pixel-hud]')

path.write_text(text, encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Write pixel HUD diagnostics to dedicated log\n", encoding="utf-8"
)
