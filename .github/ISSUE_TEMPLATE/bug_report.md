name: Bug Report
description: Report a bug in the MARA pipeline
title: "[BUG] "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for reporting a bug! Please provide as much detail as possible.
  
  - type: textarea
    id: description
    attributes:
      label: Description
      description: Clear description of the bug
      placeholder: What went wrong?
    validations:
      required: true
  
  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the bug
      placeholder: |
        1. Run command...
        2. With file...
        3. Observe error...
    validations:
      required: true
  
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What should happen
      placeholder: Expected output or behavior
    validations:
      required: true
  
  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior
      description: What actually happened
      placeholder: Actual output or error
    validations:
      required: true
  
  - type: textarea
    id: logs
    attributes:
      label: Logs/Error Messages
      description: Relevant error logs or stack traces
      render: shell
      placeholder: |
        Error message here...
        Stack trace...
  
  - type: input
    id: environment
    attributes:
      label: Environment
      placeholder: "macOS 14.0, Python 3.10, etc."
    validations:
      required: true
  
  - type: textarea
    id: additional
    attributes:
      label: Additional Context
      description: Any other relevant information
      placeholder: Screenshots, related issues, etc.
