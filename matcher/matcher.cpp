#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <queue>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {
// Explicit ASCII, no locale, no undefined behavior on bytes >= 0x80.
// Matches Python's \b for ASCII text; any UTF-8 byte counts as a boundary.
inline bool is_word_char(unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}

inline unsigned char ascii_lower(unsigned char c) {
    return (c >= 'A' && c <= 'Z') ? static_cast<unsigned char>(c - 'A' + 'a') : c;
}
}  // namespace

// Aho-Corasick: one pass over the text finds every pattern at once,
// regardless of how many patterns there are.
class TickerMatcher {
public:
    explicit TickerMatcher(
        const std::vector<std::pair<std::string, std::string>>& patterns) {
        new_node();  // root
        for (const auto& kv : patterns) add(kv.first, kv.second);
        build();
    }

    std::vector<std::string> scan(const std::string& text) const {
        std::set<std::string> found;
        const size_t n = text.size();
        int state = 0;

        for (size_t i = 0; i < n; ++i) {
            unsigned char raw = static_cast<unsigned char>(text[i]);
            unsigned char c = static_cast<unsigned char>(ascii_lower(raw));
            state = goto_[state][c];

            for (int s = state; s != 0; s = out_link_[s]) {
                for (int id : output_[s]) {
                    size_t start = i + 1 - plen_[id];
                    bool left_ok = (start == 0) ||
                        !is_word_char(static_cast<unsigned char>(text[start - 1]));
                    bool right_ok = (i + 1 == n) ||
                        !is_word_char(static_cast<unsigned char>(text[i + 1]));
                    if (left_ok && right_ok) found.insert(ticker_[id]);
                }
            }
        }
        return std::vector<std::string>(found.begin(), found.end());
    }

private:
    int new_node() {
        goto_.emplace_back();
        goto_.back().fill(-1);
        fail_.push_back(0);
        out_link_.push_back(0);
        output_.emplace_back();
        return static_cast<int>(goto_.size()) - 1;
    }

    void add(const std::string& pattern, const std::string& ticker) {
        int state = 0;
        for (char ch : pattern) {
            unsigned char c = static_cast<unsigned char>(
                ascii_lower(static_cast<unsigned char>(ch)));
            if (goto_[state][c] == -1) {
                int nxt = new_node();
                goto_[state][c] = nxt;
            }
            state = goto_[state][c];
        }
        int id = static_cast<int>(ticker_.size());
        ticker_.push_back(ticker);
        plen_.push_back(pattern.size());
        output_[state].push_back(id);
    }

    void build() {
        std::queue<int> q;
        for (int c = 0; c < 256; ++c) {
            int& t = goto_[0][c];
            if (t == -1) {
                t = 0;
            } else {
                fail_[t] = 0;
                q.push(t);
            }
        }
        while (!q.empty()) {
            int v = q.front();
            q.pop();
            out_link_[v] = output_[fail_[v]].empty() ? out_link_[fail_[v]] : fail_[v];
            for (int c = 0; c < 256; ++c) {
                int u = goto_[v][c];
                if (u == -1) {
                    goto_[v][c] = goto_[fail_[v]][c];
                } else {
                    fail_[u] = goto_[fail_[v]][c];
                    q.push(u);
                }
            }
        }
    }

    std::vector<std::array<int, 256>> goto_;
    std::vector<int> fail_;
    std::vector<int> out_link_;
    std::vector<std::vector<int>> output_;
    std::vector<std::string> ticker_;
    std::vector<size_t> plen_;
};

PYBIND11_MODULE(fastmatch, m) {
    m.doc() = "Aho-Corasick ticker matcher for NewsAct";
    py::class_<TickerMatcher>(m, "TickerMatcher")
        .def(py::init<const std::vector<std::pair<std::string, std::string>>&>())
        .def("scan", &TickerMatcher::scan);
}
