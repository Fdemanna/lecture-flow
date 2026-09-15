# Contributing to LectureFlow

Thank you for your interest in contributing to LectureFlow! We welcome contributions to help make this tool even better for the community.

## Reporting Bugs and Issues
If you encounter a bug or have a feature request, please [open an issue](https://github.com/yourusername/lectureflow/issues) and provide:
- Your operating system (macOS or Windows).
- The version of Python and Ollama you are using.
- A clear description of the issue or feature request.
- Logs or screenshots if applicable.

## Submitting Pull Requests
1. **Fork the repository** and create your branch from `main`.
2. **Make your changes** following the existing coding style.
3. **Test your code** thoroughly on your local environment (macOS or Windows, ideally both if touching platform-specific logic).
4. **Open a Pull Request** with a clear title and description explaining your changes.

### Development Guidelines
- Respect the cross-platform nature of the codebase (macOS `mlx-whisper` and Windows `faster-whisper`).
- Keep all language processing local; avoid adding dependencies on paid cloud APIs (e.g., OpenAI).
- Update the README.md if you introduce new features or requirements.

We review pull requests on a regular basis and look forward to collaborating with you!
