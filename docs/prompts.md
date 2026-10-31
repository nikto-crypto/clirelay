# Prompts and interaction

## Prompting for a value

```python
value = clirelay.prompt("Your name")
age = clirelay.prompt("Age", type=int, default=0)
```

An option can prompt when its value is missing:

```python
@clirelay.option("--name", prompt=True)
@clirelay.option("--password", prompt=True, hide_input=True,
                 confirmation_prompt=True)
```

A confirmation prompt asks twice and re-prompts if the values differ. Hidden
input is not echoed; an invalid hidden value is masked as `'***'` in the error.

## Confirmation

```python
if clirelay.confirm("Continue?"):
    ...

clirelay.confirm("Really delete?", abort=True)  # aborts if the answer is no
```

`confirm` shows `[y/N]`, `[Y/n]`, or `[y/n]` depending on the default, and loops
on invalid input.

## Aborting

Raising {class}`~clirelay.Abort`, or pressing Ctrl-C, prints `Aborted!` to stderr
and exits with status 1. Reaching end of input at a prompt does the same.

## Password option helper

```python
@clirelay.password_option()
def cli(password):
    ...
```

is shorthand for a hidden, confirmed prompt.
