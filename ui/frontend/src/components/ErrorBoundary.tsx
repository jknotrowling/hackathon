import { Component, ErrorInfo, ReactNode } from 'react';
import { Paper, Stack, Text, Title } from '@mantine/core';

type ErrorBoundaryProps = {
  children: ReactNode;
  title?: string;
};

type ErrorBoundaryState = {
  error: Error | null;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <Paper p="md" m="md" withBorder>
          <Stack gap="xs">
            <Title order={5}>{this.props.title ?? 'Something went wrong'}</Title>
            <Text size="sm" c="dimmed">
              {this.state.error.message}
            </Text>
          </Stack>
        </Paper>
      );
    }

    return this.props.children;
  }
}
