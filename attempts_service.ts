
export class AttemptsService {
    public static submitTest(data: { requestBody: any }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/attempts/submit',
            body: data.requestBody,
            mediaType: 'application/json',
            errors: {
                422: 'Validation Error',
                403: 'Free limit reached'
            }
        });
    }

    public static readAttempt(data: { id: string }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/attempts/{id}',
            path: {
                id: data.id
            },
            errors: {
                422: 'Validation Error'
            }
        });
    }

    public static getAttemptStats(): CancelablePromise<{ attempt_count: number, is_premium: boolean }> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/attempts/stats/me'
        });
    }
}
